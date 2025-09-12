#!/bin/bash

set -eo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}${1}${NC}"
}

print_success() {
    echo -e "${GREEN}${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}${1}${NC}"
}

print_error() {
    echo -e "${RED}${1}${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to generate a UUID
FALLBACK_UUID="00000000-0000-1000-8000-000000000000"
generate_uuid() {
    if command_exists python && python -c "import uuid" 2>/dev/null; then
        python -c "import uuid; print(str(uuid.uuid4()).lower())"
    elif command_exists uuidgen; then
        uuidgen | tr '[:upper:]' '[:lower:]'
    else
        # Fallback to null UUID
        echo "$FALLBACK_UUID"
    fi
}

# Function to get existing user ID or return empty
get_installation_id() {
    local identity_file="$HOME/.unpage/.identity"

    if [[ -f "$identity_file" ]]; then
        cat "$identity_file"
    else
        printf "%s" "$(generate_uuid)"
    fi
}

# Global installation ID
INSTALLATION_ID=""

# Function to persist installation ID on successful installation
persist_installation_id() {
    if [[ "${UNPAGE_TELEMETRY_DISABLED:-0}" == "1" ]]; then
        return 0
    fi

    local installation_id="$1"
    local identity_file="$HOME/.unpage/.identity"

    # Don't persist nil UUID (fallback UUID)
    if [[ "$installation_id" == "$FALLBACK_UUID" ]]; then
        return 0
    fi

    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$identity_file")"

    # Save installation ID
    printf "%s" "$installation_id" > "$identity_file"
}

# Function to send telemetry event
telemetry_event() {
    # Check if telemetry is disabled
    if [[ "${UNPAGE_TELEMETRY_DISABLED:-0}" == "1" ]]; then
        return 0
    fi

    # Wrap entire function in error handling to prevent any telemetry issues from breaking the installer
    {
        local event_name="$1"
        shift  # Remove first argument, rest are key=value pairs

        # Use session user ID and generate event ID
        local event_id
        event_id=$(generate_uuid)

        # Get system information
        local sysname
        sysname=$(uname -s 2>/dev/null || echo "unknown")
        local sysmachine
        sysmachine=$(uname -m 2>/dev/null || echo "unknown")

        # Start building the JSON payload
        local additional_fields=""

        # Process key=value pairs
        for arg in "$@"; do
            if [[ "$arg" == *"="* ]]; then
                local key="${arg%%=*}"
                local value="${arg#*=}"
                additional_fields="$additional_fields, \"$key\": \"$value\""
            fi
        done

        # Build the telemetry payload
        local telemetry_payload
        telemetry_payload=$(cat <<EOF
{
    "version": "installer",
    "sysname": "$sysname",
    "sysmachine": "$sysmachine",
    "event": "$event_name"$additional_fields
}
EOF
)

        # Choose download tool
        local download_cmd=""
        if command_exists curl; then
            download_cmd="curl"
        elif command_exists wget; then
            download_cmd="wget"
        else
            # No way to send telemetry, silently return
            return 0
        fi

        # Send the telemetry event (don't let failures break the installer)
        local tuna_url="https://tuna.aptible.com/www/e"

        if [[ "$download_cmd" == "curl" ]]; then
            curl -s -G "$tuna_url" \
                 --data-urlencode "id=$event_id" \
                 --data-urlencode "user_id=$INSTALLATION_ID" \
                 --data-urlencode "type=unpage_telemetry" \
                 --data-urlencode "url=https://github.com/aptible/unpage" \
                 --data-urlencode "value=$telemetry_payload" >/dev/null 2>&1 || true
        elif [[ "$download_cmd" == "wget" ]]; then
            local encoded_payload
            encoded_payload=$(printf '%s' "$telemetry_payload" | sed 's/ /%20/g; s/"/%22/g; s/{/%7B/g; s/}/%7D/g; s/:/%3A/g; s/,/%2C/g' 2>/dev/null || echo "")
            local encoded_event_id
            encoded_event_id=$(printf '%s' "$event_id" | sed 's/ /%20/g; s/"/%22/g; s/{/%7B/g; s/}/%7D/g; s/:/%3A/g; s/,/%2C/g' 2>/dev/null || echo "")
            local encoded_user_id
            encoded_user_id=$(printf '%s' "$INSTALLATION_ID" | sed 's/ /%20/g; s/"/%22/g; s/{/%7B/g; s/}/%7D/g; s/:/%3A/g; s/,/%2C/g' 2>/dev/null || echo "")
            wget -q -O /dev/null "$tuna_url?id=$encoded_event_id&user_id=$encoded_user_id&type=unpage_telemetry&url=https://github.com/aptible/unpage&value=$encoded_payload" >/dev/null 2>&1 || true
        fi
    } 2>/dev/null || true
}

# Function to handle script interruption/cancellation
handle_interrupt() {
    echo
    print_warning "Installation cancelled by user."
    telemetry_event 'install_cancelled'
    exit 130
}

# Trap interruption signals (Ctrl+C, SIGTERM, etc.)
trap handle_interrupt SIGINT SIGTERM

# Function to get user confirmation
confirm() {
    local prompt="$1"
    local default="${2:-N}"  # Default to "N" if not specified

    if [[ "$default" =~ ^[Yy] ]]; then
        local prompt_suffix="[Y/n]"
        local default_return=0
    else
        local prompt_suffix="[y/N]"
        local default_return=1
    fi

    while true; do
        read -r -p "$prompt $prompt_suffix: " yn < /dev/tty
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            "" ) return $default_return;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

# Function to find and source uv environment
source_uv_env() {
    # Check the possible installation locations in order of preference
    local possible_base_paths=(
        "${XDG_BIN_HOME%/bin}"  # Remove /bin if present
        "${XDG_DATA_HOME}"
        "$HOME/.local"
        "$HOME/.cargo"  # Fallback for older installations
    )

    for base_path in "${possible_base_paths[@]}"; do
        # Skip empty paths
        if [[ -z "$base_path" ]]; then
            continue
        fi

        # Look for env script in the base directory
        if [[ -f "$base_path/env" ]]; then
            print_info "Found uv environment script at: $base_path/env"
            # shellcheck disable=SC1091
            source "$base_path/env"
            return 0
        fi

        # Also check bin subdirectory for uv binary as fallback
        if [[ -f "$base_path/bin/uv" ]] && [[ -x "$base_path/bin/uv" ]]; then
            print_info "Found uv binary at: $base_path/bin/uv (adding to PATH)"
            export PATH="$base_path/bin:$PATH"
            return 0
        fi
    done

    print_warning "Could not locate uv installation or environment script."
    return 1
}

# Function to install uv
install_uv() {
    print_info "Installing uv using the official installer..."

    # Check for curl or wget
    local download_cmd=""
    if command_exists curl; then
        download_cmd="curl -LsSf"
    elif command_exists wget; then
        download_cmd="wget -qO-"
    else
        print_error "Neither curl nor wget is installed. Please install one of them and try again."
        exit 1
    fi

    # Download and run the uv installer
    if $download_cmd https://astral.sh/uv/install.sh | sh; then
        print_success "uv installed successfully!"

        # Find and source uv environment for this script execution
        if source_uv_env; then
            if command_exists uv; then
                print_success "uv is now available for this installation!"
            else
                print_warning "uv installed but may not be immediately available."
            fi
        fi

        print_info "Note: You may need to restart your shell to use uv in future sessions."
    else
        telemetry_event 'uv_install_failed'
        print_error "Failed to install uv. Please check the error messages above."
        exit 1
    fi
}

# Function to install unpage
install_unpage() {
    telemetry_event 'unpage_install_started'
    print_info "Installing unpage using uv..."

    if uv tool install unpage; then
        telemetry_event 'unpage_install_succeeded'
        print_success "unpage installed successfully!"
        print_info "You can now run 'unpage --help' to get started."
    else
        telemetry_event 'unpage_install_failed'
        print_error "Failed to install unpage. Please check the error messages above."
        exit 1
    fi
}

# Main installation logic
main() {
    # Set up session user ID (use existing or generate new)
    INSTALLATION_ID=$(get_installation_id)

    # Send telemetry event for install start
    telemetry_event 'install_started'

    echo "========================================="
    echo "          Unpage Installer"
    echo "========================================="
    echo

    # Show telemetry status to user
    if [[ "${UNPAGE_TELEMETRY_DISABLED:-0}" == "1" ]]; then
        print_info "Telemetry is disabled"
        echo
    fi

    # Check if uv is already installed
    if command_exists uv; then
        UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
        print_success "uv is already installed (${UV_VERSION})"
        telemetry_event 'uv_detected' "uv_version=$UV_VERSION"
    else
        print_warning "uv is not installed on your system."
        print_info "uv is required to install unpage. It's a fast Python package manager."
        echo
        telemetry_event 'uv_not_detected'

        if confirm "Would you like to install uv now?" "Y"; then
            telemetry_event 'uv_install_accepted'
            install_uv
            echo
        else
            telemetry_event 'uv_install_declined'
            print_info "You can install uv manually by visiting: https://docs.astral.sh/uv/getting-started/installation/"
            print_info "After installing uv, run this script again to install unpage."
            exit 0
        fi
    fi

    # Verify uv is working
    if ! command_exists uv; then
        print_error "uv installation appears to have failed or is not in PATH."
        print_info "Please restart your shell and try running this script again."
        exit 1
    fi

    # Check if unpage is already installed
    if uv tool list 2>/dev/null | grep -q "unpage"; then
        UNPAGE_VERSION=$(uv tool list 2>/dev/null | grep "unpage" | awk '{print $2}' || echo "unknown")
        print_warning "unpage appears to already be installed."
        telemetry_event 'unpage_detected' "current_version=$UNPAGE_VERSION"
        if confirm "Would you like to upgrade to the latest version?" "Y"; then
            telemetry_event 'unpage_upgrade_accepted' "current_version=$UNPAGE_VERSION"
            print_info "Upgrading unpage..."
            if uv tool upgrade unpage; then
                print_success "unpage upgraded successfully!"
            else
                print_error "Failed to upgrade unpage."
                exit 1
            fi
        else
            telemetry_event 'unpage_upgrade_declined' "current_version=$UNPAGE_VERSION"
            print_info "Skipping unpage installation."
            exit 0
        fi
    else
        install_unpage
    fi

    echo
    print_success "Installation complete!"

    # Persist installation ID on successful installation
    persist_installation_id "$INSTALLATION_ID"

    telemetry_event 'install_completed'
    print_info "Next steps:"
    echo "  1. Start a new shell session, or run 'source $HOME/.local/bin/env' to load unpage"
    echo "  2. Run 'unpage agent quickstart' to build an agent"
    echo "  3. Run 'unpage configure' to walk through the configuration wizard"
    echo "  4. Run 'unpage --help' to see all available commands"
    echo
}

# Run the main function
main "$@"
