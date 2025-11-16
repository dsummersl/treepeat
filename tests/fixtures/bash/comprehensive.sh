#!/bin/bash

# Comprehensive Bash script for testing
# This script demonstrates various bash constructs

# Variables
APP_NAME="TestApp"
VERSION="1.0.0"
CONFIG_DIR="/etc/myapp"
LOG_FILE="/var/log/myapp.log"

# Functions
function print_header() {
    echo "================================"
    echo "$1"
    echo "================================"
}

function check_dependencies() {
    local dependencies=("git" "curl" "jq")

    for dep in "${dependencies[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            echo "Error: $dep is not installed"
            return 1
        fi
    done

    return 0
}

function setup_config() {
    local config_file="$CONFIG_DIR/config.conf"

    # Create config directory if it doesn't exist
    if [ ! -d "$CONFIG_DIR" ]; then
        mkdir -p "$CONFIG_DIR"
    fi

    # Write default config
    cat > "$config_file" << EOF
app_name=$APP_NAME
version=$VERSION
debug=false
max_connections=100
EOF
}

function process_files() {
    local input_dir="$1"
    local output_dir="$2"
    local count=0

    # Process each file in directory
    for file in "$input_dir"/*.txt; do
        if [ -f "$file" ]; then
            local filename=$(basename "$file")
            cp "$file" "$output_dir/$filename"
            ((count++))
        fi
    done

    echo "Processed $count files"
}

# Main execution
main() {
    print_header "Starting $APP_NAME v$VERSION"

    # Check dependencies
    if ! check_dependencies; then
        echo "Dependency check failed"
        exit 1
    fi

    # Setup configuration
    setup_config

    # Command line argument processing
    case "$1" in
        start)
            echo "Starting application..."
            ;;
        stop)
            echo "Stopping application..."
            ;;
        restart)
            echo "Restarting application..."
            ;;
        *)
            echo "Usage: $0 {start|stop|restart}"
            exit 1
            ;;
    esac

    print_header "Completed"
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
