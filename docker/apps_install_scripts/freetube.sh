#!/bin/bash
# Build and install FreeTube inside the MCPWorld environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SUDO_PASSWORD="${SUDO_PASSWORD:-123}"

# Resolve FreeTube source directory across host or container environments.
CANDIDATE_DIRS=(
  "${FREETUBE_APP_DIR:-}"
  "$REPO_ROOT/PC-Canary/apps/FreeTube"
  "/workspace/PC-Canary/apps/FreeTube"
)

APP_DIR=""
for candidate in "${CANDIDATE_DIRS[@]}"; do
  if [[ -n "$candidate" && -d "$candidate" ]]; then
    APP_DIR="$candidate"
    break
  fi
done

if [[ -z "$APP_DIR" ]]; then
  echo "Unable to locate FreeTube sources. Set FREETUBE_APP_DIR or ensure PC-Canary submodule is present."
  exit 1
fi

BUILD_DIR="$APP_DIR/out/make"

run_with_sudo() {
  if command -v sudo >/dev/null 2>&1; then
    printf '%s\n' "$SUDO_PASSWORD" | sudo -S -- "$@"
  else
    "$@"
  fi
}

ensure_wrapper() {
  local real_bin wrapper_target="/workspace/bin/freetube"
  real_bin="$(readlink -f /usr/bin/freetube 2>/dev/null || true)"
  if [[ -z "$real_bin" || ! -x "$real_bin" ]]; then
    real_bin="$(command -v freetube 2>/dev/null || true)"
  fi
  if [[ -z "$real_bin" || ! -x "$real_bin" ]]; then
    return
  fi

  mkdir -p /workspace/bin
  cat <<EOF > "$wrapper_target"
#!/bin/bash
export ELECTRON_DISABLE_SANDBOX=1
exec "$real_bin" --no-sandbox "\$@"
EOF
  chmod 755 "$wrapper_target"

  local desktop_file=""
  local candidates=(
    "/usr/share/applications/io.freetubeapp.FreeTube.desktop"
    "/usr/share/applications/FreeTube.desktop"
    "/usr/share/applications/freetube.desktop"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      desktop_file="$candidate"
      break
    fi
  done

  if [[ -n "$desktop_file" ]]; then
    local exec_line suffix=""
    exec_line="$(grep -E '^Exec=' "$desktop_file" | head -n1 || true)"
    if [[ "$exec_line" =~ ^Exec=[^[:space:]]+([[:space:]].*)$ ]]; then
      suffix="${BASH_REMATCH[1]}"
    fi
    run_with_sudo cp "$desktop_file" "${desktop_file}.bak" >/dev/null 2>&1 || true
    run_with_sudo sed -i "s|^Exec=.*|Exec=$wrapper_target${suffix}|" "$desktop_file"

    local user_home="${HOME:-/workspace}"
    local desktop_shortcut="$user_home/Desktop/FreeTube.desktop"
    if [[ -d "$(dirname "$desktop_shortcut")" ]]; then
      cp "$desktop_file" "$desktop_shortcut" >/dev/null 2>&1 || true
      chmod +x "$desktop_shortcut" >/dev/null 2>&1 || true
    fi
  fi
}

# Skip rebuild if already available (unless forced), but refresh wrapper.
if command -v freetube >/dev/null 2>&1 && [[ -z "${FORCE_FREETUBE_INSTALL:-}" ]]; then
  echo "FreeTube already installed at $(command -v freetube); refreshed launcher."
  ensure_wrapper
  exit 0
fi

echo "Preparing Node/Yarn environment..."
if ! command -v yarn >/dev/null 2>&1; then
  if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    . "$HOME/.nvm/nvm.sh"
  fi
fi

if ! command -v yarn >/dev/null 2>&1; then
  echo "yarn command not found. Ensure Node/NVM environment is initialized before running this script."
  exit 1
fi

pushd "$APP_DIR" >/dev/null

# Track temporary dependency injection so we can roll it back.
ADDED_SOCKET_IO=0
cleanup() {
  set +e
  if [[ "$ADDED_SOCKET_IO" -eq 1 ]]; then
    echo "Restoring FreeTube dependency manifest..."
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      git checkout -- package.json yarn.lock >/dev/null 2>&1 || true
      yarn install --frozen-lockfile --check-files >/dev/null 2>&1 || true
    else
      yarn remove socket.io-client --silent >/dev/null 2>&1 || true
    fi
  fi
  popd >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Installing FreeTube dependencies..."
if [[ ! -d "node_modules" ]]; then
  yarn install --frozen-lockfile
else
  yarn install --frozen-lockfile --check-files
fi

# Ensure socket.io-client is present (required by src/main/index.js).
if ! node -e "require.resolve('socket.io-client')" >/dev/null 2>&1; then
  echo "Temporarily adding socket.io-client to satisfy build requirements..."
  yarn add socket.io-client@4.7.5 --silent
  ADDED_SOCKET_IO=1
fi

echo "Ensuring rpm build tooling is available..."
if ! command -v rpmbuild >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    run_with_sudo apt-get update >>/tmp/freetube_apt.log 2>&1 || true
    run_with_sudo apt-get install -y rpm >>/tmp/freetube_apt.log 2>&1 || true
  fi
fi

echo "Building FreeTube (this may take a few minutes)..."
yarn clean >/dev/null 2>&1 || true
set +e
yarn build
BUILD_RC=$?
set -e

# Prefer electron-builder's default output directory first
DEB_PACKAGE=""
if [ -d "$APP_DIR/build" ]; then
  DEB_PACKAGE="$(ls -1t "$APP_DIR/build"/*.deb 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "$DEB_PACKAGE" ]]; then
  DEB_PACKAGE="$(find "$BUILD_DIR" -type f -name '*.deb' -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "${DEB_PACKAGE:-}" || ! -f "$DEB_PACKAGE" ]]; then
  echo "Build did not produce a .deb package."
  echo "Tip: ensure Node/Yarn are present and consider installing 'rpm' to avoid rpm target failures."
  exit 1
fi

if [[ "$BUILD_RC" -ne 0 ]]; then
  echo "Build exited with code $BUILD_RC, but a .deb was produced at: $DEB_PACKAGE"
  echo "Proceeding with installation of the .deb."
fi

echo "Installing package $DEB_PACKAGE..."
if ! run_with_sudo dpkg -i "$DEB_PACKAGE" >>/tmp/freetube_install_dpkg.log 2>&1; then
  echo "dpkg reported missing dependencies; attempting to resolve..."
  run_with_sudo apt-get install -f -y >>/tmp/freetube_install_dpkg.log 2>&1 || true
  run_with_sudo dpkg -i "$DEB_PACKAGE" >>/tmp/freetube_install_dpkg.log 2>&1
fi

if ! command -v freetube >/dev/null 2>&1; then
  echo "FreeTube installation still requires elevated privileges."
  echo "Run the following command to finish installation manually:"
  echo "  printf '%s\\n' '$SUDO_PASSWORD' | sudo -S dpkg -i '$DEB_PACKAGE'"
  exit 1
fi

ensure_wrapper

echo "FreeTube installation complete."
