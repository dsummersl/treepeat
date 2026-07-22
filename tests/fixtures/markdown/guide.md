# Developer Guide

Examples from documentation that mirror standalone source files.

## Python Example

Compute basic statistics from a list:

```python
def calculate_stats(numbers):
    total = sum(numbers)
    count = len(numbers)
    mean = total / count
    return {"total": total, "count": count, "mean": mean}
```

## JavaScript Example

Format a date value as YYYY-MM-DD:

```javascript
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
```

## Bash Example

Verify required tools are installed:

```bash
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
```

## YAML Example

Describe a deployable service:

```yaml
service:
  name: treepeat
  port: 8080
  replicas: 3
  env:
    - LOG_LEVEL=info
    - CACHE=redis
  healthcheck:
    path: /healthz
    interval: 30
    timeout: 5
```

## Plain Text Example

This block has no language tag and should not trigger injection:

```
some plain text without a language tag
```
