#!/usr/bin/env python3
"""
Automate the MCPWorld benchmark environment setup.

This utility checks prerequisites, spins up the long-running services
needed for the evaluation stack (VNC, noVNC proxy, HTTP shim, MCP proxy,
Streamlit UI), and manages their lifecycle. Run `python tools/bootstrap_env.py --help`
for usage details.
"""

# Script overview
#
# Sections
# - Constants & paths: where logs and PIDs live; service ordering
# - Lightweight helpers: which(), ensure_dirs(), port/pid utilities
# - Process supervision: ManagedProcess for start/stop/status and readiness
# - VNC lifecycle: VNCController wrapper around TigerVNC
# - Dependency discovery: resolve_* helpers for external tools
# - Service builders: construct ManagedProcess objects (including optional Ollama)
# - CLI commands: start/stop/status/check operations
# - Parser & main: subcommand parsing and dispatch

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


# Base repo root and state directories for this supervisor.
# `.mcpworld/` is created in the repository to keep logs and pid files.
ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".mcpworld"
LOG_DIR = STATE_DIR / "logs"
PID_DIR = STATE_DIR / "pids"

# Order in which services are typically started and stopped.
# The Ollama service is optional and only included when explicitly enabled.
SERVICE_ORDER = ["vnc", "ollama", "novnc", "http", "mcp", "streamlit"]


class DependencyError(RuntimeError):
    """Raised when a required dependency is missing."""


def which(cmd: str) -> Optional[str]:
    """Return absolute path to executable or None."""
    return shutil.which(cmd)


def ensure_dirs() -> None:
    """Ensure on-disk directories exist for logs and PID files."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)


def port_is_open(host: str, port: int) -> bool:
    """Return True if a TCP connection can be established to host:port."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def read_pid(pid_file: Path) -> Optional[int]:
    """Read an integer PID from a file; return None if missing/invalid."""
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except ValueError:
        return None


def pid_is_running(pid: int) -> bool:
    """Check whether the given PID refers to a running process."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _run_manage_ollama(  # pragma: no cover - simple subprocess wrapper
    *,
    model: str,
    args: argparse.Namespace,
    keep_others: bool,
    skip_prune: bool,
) -> None:
    """Ensure the requested Ollama model is available by invoking the helper CLI."""

    manager = ROOT / "tools" / "manage_ollama_model.py"
    if not manager.exists():
        raise FileNotFoundError("manage_ollama_model.py not found; ensure tools/ is present")

    command: List[str] = [
        sys.executable,
        str(manager),
        "--model",
        model,
        "--pull",
        "--stop-running",
        "--show-status",
    ]

    if not keep_others:
        command.append("--evict-others")
    if not skip_prune:
        command.append("--prune")

    env = os.environ.copy()
    env.setdefault("OLLAMA_HOST", str(getattr(args, "ollama_host", "127.0.0.1")))
    env.setdefault("OLLAMA_PORT", str(getattr(args, "ollama_port", 11434)))

    print(f"Ensuring Ollama model '{model}' is available…")
    try:
        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as err:  # pragma: no cover
        raise RuntimeError(
            "Failed to prepare Ollama model "
            f"'{model}' (exit code {err.returncode}). "
            "Check network connectivity or verify the model tag."
        ) from err


def _print_service_hint(name: str, args: argparse.Namespace) -> None:
    """Emit human-friendly hints for interactive services."""

    if name == "vnc":
        print(
            f"VNC server starting on display {args.vnc_display} (port {args.vnc_port}). "
            "If prompted, set a password for this session."
        )
        return

    if name == "novnc":
        print(
            "noVNC web client available once ready: "
            f"http://localhost:{args.novnc_port}/vnc.html"
        )
        return

    if name == "http":
        print(
            "HTTP shim starting; combined desktop/Streamlit index will be served on "
            f"http://localhost:{args.http_port}"
        )
        return

    if name == "mcp":
        print(
            "MCP proxy listening on port "
            f"{args.mcp_port}; configure MCP clients to connect to localhost:{args.mcp_port}."
        )
        return

    if name == "streamlit":
        print(
            "Streamlit UI launching; once ready visit "
            f"http://localhost:{args.streamlit_port}. "
            "Initial start can take a moment; check streamlit.log if the page is blank."
        )


@dataclass
class ManagedProcess:
    """Supervise a child process: logs, PID tracking, readiness.

    - Executes the given `command` in its own process group (so SIGTERM can
      stop the whole tree).
    - Redirects stdout/stderr to `log_file` (append mode).
    - Persists the spawned PID into a PID file for later stop/status calls.
    - Optionally polls `readiness_check` until success or timeout.
    """
    name: str
    command: List[str]
    cwd: Path
    log_file: Path
    env: Dict[str, str] = field(default_factory=dict)
    readiness_check: Optional[Callable[[], bool]] = None
    readiness_timeout: float = 20.0
    pid_file: Path = field(init=False)

    def __post_init__(self) -> None:
        self.pid_file = PID_DIR / f"{self.name}.pid"

    def is_running(self) -> bool:
        pid = read_pid(self.pid_file)
        return bool(pid and pid_is_running(pid))

    def start(self, *, dry_run: bool = False) -> None:
        command_str = " ".join(self.command)
        if dry_run:
            print(f"[dry-run] {self.name}: {command_str}")
            return
        if self.is_running():
            print(f"{self.name}: already running (pid {read_pid(self.pid_file)})")
            return

        ensure_dirs()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        merged_env = os.environ.copy()
        merged_env.update(self.env)

        with open(self.log_file, "ab", buffering=0) as log_handle:
            proc = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=merged_env,
                preexec_fn=os.setsid,
            )
        self.pid_file.write_text(str(proc.pid))
        print(f"{self.name}: launched (pid {proc.pid}) -> {self.log_file}")

        if self.readiness_check:
            self._wait_for_ready()

    def _wait_for_ready(self) -> None:
        if not self.readiness_check:
            return
        deadline = time.time() + self.readiness_timeout
        while time.time() < deadline:
            if self.readiness_check():
                print(f"{self.name}: ready")
                return
            if not self.is_running():
                print(f"{self.name}: process exited before becoming ready")
                return
            time.sleep(0.5)
        print(f"{self.name}: readiness check timed out after {self.readiness_timeout}s")

    def stop(self, *, silent: bool = False) -> None:
        pid = read_pid(self.pid_file)
        if not pid or not pid_is_running(pid):
            if not silent:
                print(f"{self.name}: not running")
            self.pid_file.unlink(missing_ok=True)
            return
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            if not silent:
                print(f"{self.name}: process already terminated")
        else:
            if not silent:
                print(f"{self.name}: sent SIGTERM to process group {pid}")
        self.pid_file.unlink(missing_ok=True)

    def status(self) -> str:
        pid = read_pid(self.pid_file)
        if not pid:
            return "stopped"
        return "running" if pid_is_running(pid) else "stale-pid"


class VNCController:
    """Control TigerVNC sessions (start/stop/status) on a given display.

    `vncserver` manages session state internally, so we do not treat it as a
    child process under our PID supervision. This wrapper uses `vncserver`
    subcommands to manage the lifecycle.
    """
    def __init__(self, binary: str, display: str, geometry: str, xstartup: Optional[Path]):
        self.binary = binary
        self.display = display
        self.geometry = geometry
        self.xstartup = xstartup

    def _run(self, args: Iterable[str]) -> subprocess.CompletedProcess[str]:
        command = [self.binary, *args]
        return subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def start(self) -> None:
        args: List[str] = ["-geometry", self.geometry]
        if self.xstartup and self.xstartup.exists():
            args.extend(["-xstartup", str(self.xstartup)])
        result = self._run([*args, self.display])
        if result.returncode != 0:
            if "already running" in result.stderr.lower():
                print(f"vnc: existing session detected on {self.display}")
            else:
                raise RuntimeError(f"vnc: failed to start ({result.stderr.strip()})")
        else:
            print(f"vnc: started display {self.display}")

    def stop(self) -> None:
        result = self._run(["-kill", self.display])
        if result.returncode != 0 and "no matching" not in result.stderr.lower():
            print(f"vnc: failed to stop ({result.stderr.strip()})")
        else:
            print(f"vnc: stopped {self.display}")

    def status(self) -> str:
        result = self._run(["-list"])
        if result.returncode != 0:
            return "unknown"
        return "running" if self.display in result.stdout else "stopped"


def resolve_vnc_binary() -> str:
    """Locate `vncserver` or raise DependencyError if not found."""
    path = which("vncserver")
    if not path:
        raise DependencyError("vncserver not found. Install TigerVNC or ensure it is on PATH.")
    return path


def resolve_novnc_proxy() -> str:
    """Find noVNC proxy entrypoint across common install paths."""
    candidates = [
        which("novnc_proxy"),
        "/opt/noVNC/utils/novnc_proxy",
        "/usr/share/novnc/utils/novnc_proxy",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise DependencyError("noVNC proxy not found. Install noVNC or adjust --novnc-cmd.")


def resolve_mcp_proxy() -> str:
    """Find the MCP proxy binary (`mcp-proxy`)."""
    path = which("mcp-proxy")
    if not path:
        raise DependencyError("mcp-proxy not found. Install via `pip install mcp-proxy`.")
    return path


def resolve_uvx() -> str:
    """Find `uvx` (from `uv`) used to launch MCP servers."""
    path = which("uvx")
    if not path:
        raise DependencyError("uvx not found. Install uv (https://github.com/astral-sh/uv).")
    return path


def resolve_ollama() -> str:
    """Locate the Ollama CLI binary."""
    path = which("ollama")
    if not path:
        raise DependencyError("ollama binary not found. Install Ollama or set --ollama-cmd.")
    return path


def build_managed_services(args: argparse.Namespace) -> tuple[Dict[str, ManagedProcess], Dict[str, str]]:
    """Build ManagedProcess objects and report missing services.

    Returns:
        (services, missing)
        - services: Map of service name to ManagedProcess that can be started.
        - missing: Map of service name to a human-readable reason.
    """
    services: Dict[str, ManagedProcess] = {}
    missing: Dict[str, str] = {}
    host = "127.0.0.1"

    ollama_requested = getattr(args, "enable_ollama", False)
    if getattr(args, "only", None) and "ollama" in args.only:
        ollama_requested = True

    if ollama_requested:
        try:
            ollama_cmd = args.ollama_cmd or resolve_ollama()
        except DependencyError as err:
            missing["ollama"] = str(err)
        else:
            ollama_host = args.ollama_host
            ollama_port = args.ollama_port
            ollama_env = {
                "OLLAMA_HOST": str(ollama_host),
                "OLLAMA_PORT": str(ollama_port),
            }
            services["ollama"] = ManagedProcess(
                name="ollama",
                command=[
                    ollama_cmd,
                    "serve",
                ],
                cwd=ROOT,
                log_file=LOG_DIR / "ollama.log",
                readiness_check=lambda host=ollama_host, port=ollama_port: port_is_open(host, port),
                readiness_timeout=90.0,
                env=ollama_env,
            )
    try:
        novnc_cmd = args.novnc_cmd or resolve_novnc_proxy()
    except DependencyError as err:
        missing["novnc"] = str(err)
    else:
        services["novnc"] = ManagedProcess(
            name="novnc",
            command=[
                novnc_cmd,
                "--vnc",
                f"{host}:{args.vnc_port}",
                "--listen",
                f"0.0.0.0:{args.novnc_port}",
                "--web",
                args.novnc_web,
            ],
            cwd=ROOT,
            log_file=LOG_DIR / "novnc.log",
            readiness_check=lambda: port_is_open(host, args.novnc_port),
        )

    services["http"] = ManagedProcess(
        name="http",
        command=[
            sys.executable,
            str(ROOT / "computer-use-demo" / "image" / "http_server.py"),
        ],
        cwd=ROOT / "computer-use-demo",
        log_file=LOG_DIR / "http.log",
        readiness_check=lambda: port_is_open(host, args.http_port),
    )

    try:
        mcp_proxy_cmd = args.mcp_proxy_cmd or resolve_mcp_proxy()
    except DependencyError as err:
        missing["mcp"] = str(err)
        mcp_proxy_cmd = None
    else:
        try:
            uvx_cmd = args.uvx_cmd or resolve_uvx()
        except DependencyError as err:
            missing["mcp"] = str(err)
            uvx_cmd = None
    if mcp_proxy_cmd and uvx_cmd:
        services["mcp"] = ManagedProcess(
            name="mcp",
            command=[
                mcp_proxy_cmd,
                "--host",
                "0.0.0.0",
                "--port",
                str(args.mcp_port),
                uvx_cmd,
                "mcp-server-fetch",
            ],
            cwd=ROOT,
            log_file=LOG_DIR / "mcp_proxy.log",
            readiness_check=lambda: port_is_open(host, args.mcp_port),
        )

    # Environment for the Streamlit UI: controls provider + OpenAI-compatible
    # settings that the app reads on startup. Also propagate desktop geometry
    # and display number so the Computer tool can target the correct X display.
    streamlit_env: Dict[str, str] = {
        "STREAMLIT_SERVER_PORT": str(args.streamlit_port),
    }
    # Parse VNC geometry (e.g., 1280x800) and display (e.g., :4)
    try:
        width_str, height_str = str(args.vnc_geometry).lower().split("x", 1)
        if width_str.isdigit() and height_str.isdigit():
            streamlit_env["WIDTH"] = width_str
            streamlit_env["HEIGHT"] = height_str
    except Exception:
        # Leave unset if parsing fails; Computer tool will assert if missing
        pass
    display_str = str(args.vnc_display)
    if display_str.startswith(":") and len(display_str) > 1 and display_str[1:].isdigit():
        streamlit_env["DISPLAY_NUM"] = display_str[1:]
        # Also export DISPLAY for any subprocesses/tools that rely on it implicitly
        streamlit_env["DISPLAY"] = display_str
    provider = getattr(args, "provider", None)
    if provider:
        # Streamlit expects lowercase provider identifiers matching APIProvider values
        streamlit_env["API_PROVIDER"] = str(provider).lower()
    anthropic_key = getattr(args, "anthropic_api_key", None)
    if anthropic_key:
        streamlit_env["ANTHROPIC_API_KEY"] = anthropic_key
    openai_key = getattr(args, "openai_api_key", None)
    if openai_key:
        streamlit_env["OPENAI_API_KEY"] = openai_key
    openai_base_url = getattr(args, "openai_base_url", None)
    if openai_base_url:
        streamlit_env["OPENAI_BASE_URL"] = openai_base_url
    elif getattr(args, "enable_ollama", False):
        streamlit_env["OPENAI_BASE_URL"] = f"http://{args.ollama_host}:{args.ollama_port}"
    openai_endpoint = getattr(args, "openai_endpoint", None)
    if openai_endpoint:
        streamlit_env["OPENAI_ENDPOINT"] = openai_endpoint
    elif getattr(args, "enable_ollama", False):
        streamlit_env.setdefault("OPENAI_ENDPOINT", "/v1/chat/completions")
    openai_tool_choice = getattr(args, "openai_tool_choice", None)
    if openai_tool_choice:
        streamlit_env["OPENAI_TOOL_CHOICE"] = openai_tool_choice
    openai_timeout = getattr(args, "openai_timeout", None)
    if openai_timeout is not None:
        streamlit_env["OPENAI_TIMEOUT"] = str(openai_timeout)
    openai_response_format = getattr(args, "openai_response_format", None)
    if openai_response_format:
        streamlit_env["OPENAI_RESPONSE_FORMAT"] = openai_response_format

    # Ensure Streamlit runs headless and skips telemetry prompts since it
    # launches in the background without an interactive stdin.
    streamlit_env.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    streamlit_env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    services["streamlit"] = ManagedProcess(
        name="streamlit",
        command=[
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "computer-use-demo" / "computer_use_demo" / "streamlit.py"),
        ],
        cwd=ROOT / "computer-use-demo",
        log_file=LOG_DIR / "streamlit.log",
        env=streamlit_env,
        readiness_check=lambda: port_is_open(host, args.streamlit_port),
        readiness_timeout=60.0,
    )

    return services, missing


def format_status(name: str, status: str) -> str:
    """Format a status line for human-readable output."""
    return f"{name:10s} {status}"


def run_check(args: argparse.Namespace) -> int:
    """Check presence of key dependencies and print results.

    Returns 0 if all probes pass; non-zero if any are missing/broken.
    """
    checks = {
        "python": lambda: True,
        "vncserver": lambda: bool(resolve_vnc_binary()),
        "novnc_proxy": lambda: bool(resolve_novnc_proxy()),
        "mcp-proxy": lambda: bool(resolve_mcp_proxy()),
        "uvx": lambda: bool(resolve_uvx()),
        # Desktop interaction dependencies
        "xdotool": lambda: bool(which("xdotool")),
        "screenshot_tool": lambda: bool(which("gnome-screenshot") or which("scrot") or which("import") or which("xwd")),
        "streamlit": lambda: subprocess.run(
            [sys.executable, "-m", "streamlit", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0,
    }
    if getattr(args, "enable_ollama", False):
        checks["ollama"] = lambda: bool(resolve_ollama())
    failures: Dict[str, str] = {}
    for name, probe in checks.items():
        try:
            ok = probe()
        except DependencyError as err:
            failures[name] = str(err)
            continue
        if not ok:
            failures[name] = "probe failed"

    if not failures:
        print("All dependencies satisfied.")
        return 0
    print("Missing or broken dependencies:")
    for dep, reason in failures.items():
        print(f"  - {dep}: {reason}")
    return 1


def select_services(args: argparse.Namespace) -> List[str]:
    """Compute target service list honoring --only/--skip, preserving order."""
    names = SERVICE_ORDER.copy()
    if args.only:
        names = list(dict.fromkeys(args.only))
    if args.skip:
        names = [name for name in names if name not in set(args.skip)]
    ollama_requested = getattr(args, "enable_ollama", False)
    if args.only and "ollama" in args.only:
        ollama_requested = True
    if "ollama" in names and not ollama_requested:
        names = [name for name in names if name != "ollama"]
    return names


def start_services(args: argparse.Namespace) -> int:
    """Start selected services with readiness checks.

    VNC is handled first via VNCController (if requested), then each
    ManagedProcess is started in order. Missing dependencies can be fatal
    when --strict is set.
    """
    ensure_dirs()
    selected = select_services(args)

    try:
        vnc_binary = resolve_vnc_binary()
    except DependencyError as err:
        if "vnc" in selected:
            print(err)
            if args.strict:
                return 1
            print("Skipping VNC startup.")
            selected = [name for name in selected if name != "vnc"]
        vnc_binary = None  # type: ignore[assignment]

    services: Dict[str, ManagedProcess] = {}
    missing: Dict[str, str] = {}
    services, missing = build_managed_services(args)
    if missing:
        for name, reason in missing.items():
            print(f"{name}: {reason}")
            if args.strict:
                return 1

    # Start VNC first if requested.
    if "vnc" in selected and vnc_binary:
        xstartup = Path(args.vnc_xstartup) if args.vnc_xstartup else None
        controller = VNCController(
            binary=vnc_binary,
            display=args.vnc_display,
            geometry=args.vnc_geometry,
            xstartup=xstartup,
        )
        _print_service_hint("vnc", args)
        try:
            controller.start()
        except RuntimeError as err:
            print(err)
            if args.strict:
                return 1

    for name in selected:
        if name == "vnc":
            continue
        service = services.get(name)
        if not service:
            print(f"{name}: not configured (dependency missing?)")
            if args.strict:
                return 1
            continue
        try:
            _print_service_hint(name, args)
            service.start(dry_run=args.dry_run)
            if (
                name == "ollama"
                and not args.dry_run
                and getattr(args, "ollama_model", None)
            ):
                _run_manage_ollama(
                    model=args.ollama_model,
                    args=args,
                    keep_others=getattr(args, "ollama_keep_others", False),
                    skip_prune=getattr(args, "ollama_no_prune", False),
                )
        except FileNotFoundError as err:
            print(f"{name}: failed to launch ({err})")
            if args.strict:
                return 1
    return 0


def stop_services(args: argparse.Namespace) -> int:
    """Stop selected services and clean up PID files; stop VNC if selected."""
    selected = select_services(args)
    exit_code = 0

    # Stop managed processes first.
    services, _ = build_managed_services(args)

    for name in selected:
        if name == "vnc":
            continue
        service = services.get(name)
        if service:
            service.stop()
        else:
            pid_file = PID_DIR / f"{name}.pid"
            pid_file.unlink(missing_ok=True)

    if "vnc" in selected:
        try:
            vnc_binary = resolve_vnc_binary()
        except DependencyError as err:
            print(err)
            return exit_code
        controller = VNCController(
            binary=vnc_binary,
            display=args.vnc_display,
            geometry=args.vnc_geometry,
            xstartup=None,
        )
        controller.stop()
    return exit_code


def status_services(args: argparse.Namespace) -> int:
    """Print status for selected services (running/stopped/missing)."""
    selected = select_services(args)
    rows: List[str] = []

    services, missing = build_managed_services(args)

    for name in selected:
        if name == "vnc":
            try:
                vnc_binary = resolve_vnc_binary()
            except DependencyError:
                rows.append(format_status("vnc", "missing"))
                continue
            controller = VNCController(
                binary=vnc_binary,
                display=args.vnc_display,
                geometry=args.vnc_geometry,
                xstartup=None,
            )
            rows.append(format_status("vnc", controller.status()))
        elif missing and name in missing:
            rows.append(format_status(name, "missing"))
        else:
            service = services.get(name)
            if not service:
                rows.append(format_status(name, "missing"))
            else:
                rows.append(format_status(name, service.status()))
    print("\n".join(rows))
    return 0


def make_parser() -> argparse.ArgumentParser:
    """Create argparse parser with subcommands and common flags."""
    parser = argparse.ArgumentParser(description="MCPWorld environment bootstrapper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--only",
            choices=SERVICE_ORDER,
            action="append",
            help="Limit action to specific service(s).",
        )
        subparser.add_argument(
            "--skip",
            choices=SERVICE_ORDER,
            action="append",
            help="Skip specific services.",
        )
        subparser.add_argument(
            "--vnc-display",
            default=":4",
            help="VNC display identifier (default :4).",
        )
        subparser.add_argument(
            "--vnc-geometry",
            default="1024x768",
            help="VNC geometry (resolution).",
        )
        subparser.add_argument(
            "--vnc-port",
            type=int,
            default=5904,
            help="VNC TCP port for the agent desktop (default 5904).",
        )
        subparser.add_argument(
            "--novnc-port",
            type=int,
            default=6080,
            help="noVNC WebSocket port (default 6080).",
        )
        subparser.add_argument(
            "--http-port",
            type=int,
            default=8081,
            help="Port for the HTTP shim (default 8081).",
        )
        subparser.add_argument(
            "--mcp-port",
            type=int,
            default=6010,
            help="Port for the MCP proxy (default 6010).",
        )
        subparser.add_argument(
            "--streamlit-port",
            type=int,
            default=8501,
            help="Streamlit server port (default 8501).",
        )
        subparser.add_argument(
            "--novnc-web",
            default="/opt/noVNC",
            help="Path to noVNC static assets (default /opt/noVNC).",
        )
        subparser.add_argument(
            "--novnc-cmd",
            help="Explicit path to novnc_proxy executable.",
        )
        subparser.add_argument(
            "--mcp-proxy-cmd",
            help="Explicit path to mcp-proxy executable.",
        )
        subparser.add_argument(
            "--uvx-cmd",
            help="Explicit path to uvx executable.",
        )
        subparser.add_argument(
            "--enable-ollama",
            action="store_true",
            help="Start/stop the Ollama server alongside other services.",
        )
        subparser.add_argument(
            "--ollama-cmd",
            help="Explicit path to the ollama binary (defaults to PATH lookup).",
        )
        subparser.add_argument(
            "--ollama-host",
            default="127.0.0.1",
            help="Host/interface for Ollama serve (default 127.0.0.1).",
        )
        subparser.add_argument(
            "--ollama-port",
            type=int,
            default=11434,
            help="TCP port for Ollama serve (default 11434).",
        )
        subparser.add_argument(
            "--ollama-model",
            help="Ensure the specified Ollama model is pulled before other services start.",
        )
        subparser.add_argument(
            "--ollama-keep-others",
            action="store_true",
            help="Do not remove other Ollama models when preparing the requested model.",
        )
        subparser.add_argument(
            "--ollama-no-prune",
            action="store_true",
            help="Skip running `ollama prune` after model preparation.",
        )

    start_parser = subparsers.add_parser("start", help="Start services")
    add_common_arguments(start_parser)
    start_parser.add_argument(
        "--vnc-xstartup",
        default=str(Path.home() / ".vnc" / "xstartup"),
        help="Path to xstartup script for VNC (default ~/.vnc/xstartup).",
    )
    start_parser.add_argument(
        "--provider",
        choices=["anthropic", "openai"],
        help="Default provider passed to downstream apps.",
    )
    start_parser.add_argument(
        "--anthropic-api-key",
        help="Anthropic API key for downstream services.",
    )
    start_parser.add_argument(
        "--openai-api-key",
        help="OpenAI-compatible API key for downstream services.",
    )
    start_parser.add_argument(
        "--openai-base-url",
        help="Override OpenAI-compatible base URL.",
    )
    start_parser.add_argument(
        "--openai-endpoint",
        help="Override OpenAI-compatible endpoint path.",
    )
    start_parser.add_argument(
        "--openai-tool-choice",
        help="Override OpenAI tool_choice behaviour (auto/none).",
    )
    start_parser.add_argument(
        "--openai-timeout",
        type=float,
        help="Timeout value passed to the OpenAI adapter.",
    )
    start_parser.add_argument(
        "--openai-response-format",
        help="Response format override for OpenAI adapter.",
    )
    start_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    start_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit immediately if a dependency is missing.",
    )

    stop_parser = subparsers.add_parser("stop", help="Stop services")
    add_common_arguments(stop_parser)

    status_parser = subparsers.add_parser("status", help="Report service status")
    add_common_arguments(status_parser)

    subparsers.add_parser("check", help="Check runtime dependencies")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point: parse args and dispatch to subcommand handlers."""
    parser = make_parser()
    args = parser.parse_args(argv)

    if args.command == "start":
        return start_services(args)
    if args.command == "stop":
        return stop_services(args)
    if args.command == "status":
        return status_services(args)
    if args.command == "check":
        return run_check(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
