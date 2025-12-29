#!/bin/bash
# gstack installer script
# Usage: curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/scripts/install.sh | bash

set -e

# Configuration
REPO_OWNER="nicomalacho"
REPO_NAME="stack-branch"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}==>${NC} $1"
}

warn() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

error() {
    echo -e "${RED}Error:${NC} $1" >&2
    exit 1
}

# Detect OS and architecture
detect_platform() {
    local os arch

    case "$(uname -s)" in
        Darwin)
            os="macos"
            ;;
        Linux)
            os="linux"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            os="windows"
            ;;
        *)
            error "Unsupported operating system: $(uname -s)"
            ;;
    esac

    case "$(uname -m)" in
        x86_64|amd64)
            arch="x86_64"
            ;;
        arm64|aarch64)
            arch="arm64"
            ;;
        *)
            error "Unsupported architecture: $(uname -m)"
            ;;
    esac

    # macOS arm64 is only available on Apple Silicon
    if [ "$os" = "macos" ] && [ "$arch" = "arm64" ]; then
        ARTIFACT_NAME="gs-macos-arm64"
    elif [ "$os" = "macos" ]; then
        ARTIFACT_NAME="gs-macos-x86_64"
    elif [ "$os" = "linux" ]; then
        ARTIFACT_NAME="gs-linux-x86_64"
    elif [ "$os" = "windows" ]; then
        ARTIFACT_NAME="gs-windows-x86_64.exe"
    fi

    echo "$ARTIFACT_NAME"
}

# Get the latest release URL
get_download_url() {
    local artifact_name="$1"
    echo "https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/latest/download/${artifact_name}"
}

# Main installation
main() {
    info "Detecting platform..."
    local artifact_name
    artifact_name=$(detect_platform)
    info "Platform: $artifact_name"

    local download_url
    download_url=$(get_download_url "$artifact_name")
    info "Downloading from: $download_url"

    # Create temp directory
    local tmp_dir
    tmp_dir=$(mktemp -d)
    trap "rm -rf $tmp_dir" EXIT

    # Download
    local tmp_file="$tmp_dir/gs"
    if command -v curl &> /dev/null; then
        curl -fsSL "$download_url" -o "$tmp_file"
    elif command -v wget &> /dev/null; then
        wget -q "$download_url" -O "$tmp_file"
    else
        error "Neither curl nor wget found. Please install one of them."
    fi

    # Make executable
    chmod +x "$tmp_file"

    # Install
    info "Installing to $INSTALL_DIR/gs..."
    if [ -w "$INSTALL_DIR" ]; then
        mv "$tmp_file" "$INSTALL_DIR/gs"
    else
        warn "Elevated permissions required to install to $INSTALL_DIR"
        sudo mv "$tmp_file" "$INSTALL_DIR/gs"
    fi

    # Verify installation
    if command -v gs &> /dev/null; then
        info "Installation complete!"
        echo ""
        echo "Run 'gs --help' to get started."
    else
        warn "Installation complete, but 'gs' is not in your PATH."
        echo "Add $INSTALL_DIR to your PATH or run: $INSTALL_DIR/gs --help"
    fi
}

main "$@"
