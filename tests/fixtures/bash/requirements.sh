function check_requirements() {
    local tools=("git" "curl" "jq")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            echo "Missing: $tool"
            return 1
        fi
    done
    return 0
}
