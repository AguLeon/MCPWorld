#!/usr/bin/env bash

# entrypoint.sh - Main entry point for OpenMCP

set -euo pipefail

# ─── Colors & Helpers ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info() { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- ${SCRIPT_DIR}/.. && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.cfg"
DOCKER_DIR="${BASE_DIR}/docker"
APPS_DIR="${DOCKER_DIR}/apps_install_scripts"

# Ensure config.cfg exists with required env variables ────────────
setup_config() {
    info "Checking configuration file: ${CONFIG_FILE}"

    if [[ ! -f "${CONFIG_FILE}" ]]; then
        warn "config.cfg not found. Creating with default values..."
        cat >"${CONFIG_FILE}" <<EOF
# MCPBench Configuration
# Screen resolution for the virtual display
WIDTH=1000
HEIGHT=1000
EOF
        success "Created config.cfg with defaults (WIDTH=1000, HEIGHT=1000)"
    fi

    # Source the config
    # shellcheck disable=SC1090
    source "${CONFIG_FILE}"

    # Ensure WIDTH and HEIGHT are set
    if [[ -z "${WIDTH:-}" ]]; then
        warn "WIDTH not set in config.cfg. Setting default: 1000"
        echo "WIDTH=1000" >>"${CONFIG_FILE}"
        WIDTH=1000
    fi
    if [[ -z "${HEIGHT:-}" ]]; then
        warn "HEIGHT not set in config.cfg. Setting default: 1000"
        echo "HEIGHT=1000" >>"${CONFIG_FILE}"
        HEIGHT=1000
    fi

    export WIDTH HEIGHT
    success "Configuration loaded: WIDTH=${WIDTH}, HEIGHT=${HEIGHT}"
}

# ─── Step 1: Start Docker Compose Containers ────────────────────────────────
start_containers() {
    info "Starting docker-compose containers..."

    if ! command -v docker &>/dev/null; then
        error "Docker is not installed or not in PATH. Please install Docker first."
        exit 1
    fi

    cd "${DOCKER_DIR}"

    # Export variables so docker-compose can pick them up
    export WIDTH HEIGHT

    export OLLAMA_DEBUG
    export OLLAMA_HOST
    export OLLAMA_CONTEXT_LENGTH
    export OLLAMA_KEEP_ALIVE
    export OLLAMA_MAX_QUEUE
    export OLLAMA_MAX_LOADED_MODELS
    export OLLAMA_MODELS
    export OLLAMA_NUM_PARALLEL
    export OLLAMA_NOPRUNE
    export OLLAMA_ORIGINS
    export OLLAMA_SCHED_SPREAD
    export OLLAMA_FLASH_ATTENTION
    export OLLAMA_KV_CACHE_TYPE
    export # OLLAMA_LLM_LIBRARY
    export OLLAMA_GPU_OVERHEAD
    export OLLAMA_LOAD_TIMEOUT

    docker compose up -d --build

    info "Waiting for containers to be ready..."
    sleep 5

    # Verify the mcpworld container is running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        success "Container '${CONTAINER_NAME}' is up and running."
    else
        error "Container '${CONTAINER_NAME}' failed to start. Check docker logs."
        docker compose logs "${CONTAINER_NAME}"
        exit 1
    fi

    cd "${SCRIPT_DIR}"
}

# Install Apps into the container ────────────────────────
check_app_installed() {
    local app_name="$1"
    # Check if the app's marker file exists or if the binary is present
    docker exec "${CONTAINER_NAME}" bash -c "
        if command -v '${app_name}' &> /dev/null 2>&1; then
            exit 0
        elif [[ -f /opt/.installed_${app_name} ]]; then
            exit 0
        else
            exit 1
        fi
    " 2>/dev/null
}

install_apps() {
    if [[ ! -d "${APPS_DIR}" ]]; then
        warn "Apps install directory not found at ${APPS_DIR}. Skipping app installation."
        return
    fi

    local install_scripts=()
    while IFS= read -r -d '' script; do
        install_scripts+=("$script")
    done < <(find "${APPS_DIR}" -maxdepth 1 -name "*.sh" -type f -print0 | sort -z)

    if [[ ${#install_scripts[@]} -eq 0 ]]; then
        warn "No install scripts found in ${APPS_DIR}. Skipping."
        return
    fi

    echo ""
    info "The following apps are available for installation into '${CONTAINER_NAME}':"
    echo "──────────────────────────────────────────────────"
    for script in "${install_scripts[@]}"; do
        local app_name
        app_name="$(basename "${script}" .sh)"
        # Replace common prefixes like "install_"
        app_name="${app_name#install_}"

        if check_app_installed "${app_name}"; then
            echo -e "  ${GREEN}✔${NC} ${app_name} (already installed)"
        else
            echo -e "  ${YELLOW}○${NC} ${app_name} (not installed)"
        fi
    done
    echo "──────────────────────────────────────────────────"
    echo ""

    read -rp "$(echo -e "${CYAN}Would you like to install the apps listed above? (y/N): ${NC}")" install_choice

    if [[ "${install_choice}" =~ ^[Yy]$ ]]; then
        for script in "${install_scripts[@]}"; do
            local app_name
            app_name="$(basename "${script}" .sh)"
            app_name="${app_name#install_}"

            if check_app_installed "${app_name}"; then
                success "${app_name} is already installed. Skipping."
                continue
            fi

            info "Installing ${app_name} into '${CONTAINER_NAME}'..."

            # Warn about potentially long installs
            case "${app_name}" in
            *vscode* | *code* | *VSCode*)
                warn "Installing ${app_name} can take a while. Please be patient..."
                ;;
            *chrome* | *firefox* | *browser*)
                warn "Installing ${app_name} may take some time..."
                ;;
            esac

            # # Run the script to install it
            # docker exec "${CONTAINER_NAME}" bash -c "
            #     /workspace/MCPWorld/docker/apps_install_scripts/${app_name}.sh
            # "
            # Copy the script into the container and execute it
            docker cp "${script}" "${CONTAINER_NAME}:/tmp/install_${app_name}.sh"
            docker exec "${CONTAINER_NAME}" bash -c "
                chmod +x /tmp/install_${app_name}.sh && \
                /tmp/install_${app_name}.sh && \
                touch /opt/.installed_${app_name} && \
                rm -f /tmp/install_${app_name}.sh
            "

            if [[ $? -eq 0 ]]; then
                success "${app_name} installed successfully."
            else
                error "Failed to install ${app_name}. Check container logs for details."
            fi
        done
    else
        info "Skipping app installation."
    fi
}

# Run Benchmark ───────────────────────────────────────────────────
run_benchmark() {
    echo ""
    info "──────────────────────────────────────────────────"
    info "  Benchmark Runner"
    info "──────────────────────────────────────────────────"
    echo ""
    echo "  This will run the full multi-model benchmark with:"
    echo "    ./run_multi_model_benchmark.sh both ${INFRASTRUCTURE_TAG}"
    echo ""

    read -rp "$(echo -e "${CYAN}Would you like to run the benchmark now? (y/N): ${NC}")" bench_choice

    if [[ "${bench_choice}" =~ ^[Yy]$ ]]; then
        info "Starting full benchmark run..."
        warn "This may take a significant amount of time depending on the models configured."
        echo ""

        if [[ -f "${SCRIPT_DIR}/run_multi_model_benchmark.sh" ]]; then
            chmod +x "${SCRIPT_DIR}/run_multi_model_benchmark.sh"
            "${SCRIPT_DIR}/run_multi_model_benchmark.sh" both "${INFRASTRUCTURE_TAG}"
        else
            error "run_multi_model_benchmark.sh not found in ${SCRIPT_DIR}"
            exit 1
        fi

        success "Benchmark run complete!"
    else
        info "Skipping benchmark. You can run it later with:"
        echo "    ./run_multi_model_benchmark.sh both ${INFRASTRUCTURE_TAG}"
    fi
}

# Main ────────────────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 <infrastructure_tag>"
    echo ""
    echo "  infrastructure_tag   Tag identifying the infrastructure being benchmarked"
    echo ""
    echo "Example:"
    echo "  $0 my_cloud_setup"
    exit 1
}

main() {
    if [[ $# -lt 1 ]]; then
        error "Missing required argument: infrastructure_tag"
        usage
    fi

    INFRASTRUCTURE_TAG="$1"

    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║            OpenMCP - Setup & Launch              ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    info "Infrastructure tag: ${INFRASTRUCTURE_TAG}"
    echo ""

    setup_config
    echo ""

    start_containers
    echo ""

    install_apps
    echo ""

    run_benchmark
    echo ""

}
success "All done!"

main "$@"
