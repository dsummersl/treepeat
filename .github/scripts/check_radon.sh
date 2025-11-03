#!/bin/bash

# nounset: undefined variable outputs error message, and forces an exit
set -u
# errexit: abort script at first error
set -e

echo "Radon Cyclomatic Complexity below grade A:"
PACKAGE="tssim"
CC_COMMAND="uv run radon cc -n B ${PACKAGE}"
CC=$($CC_COMMAND)
$CC_COMMAND

echo "Radon Maintainability Index below grade A:"
MI_COMMAND="uv run radon mi -n B ${PACKAGE}"
MI=$($MI_COMMAND)
$MI_COMMAND

MAX_LINE_LENGTH=80
echo "Lines of Code over $MAX_LINE_LENGTH lines:"
L=$(uv run radon cc --json "${PACKAGE}" | jq -r 'to_entries[] |
  .key as $file |
  .value[] |
  select(.type == "method" or .type == "function") |
  (.endline - .lineno + 1) as $length |
  select($length > 80) |
  "\($file):\(.lineno) - \(.name) (\($length) lines)"
')
echo "$L"


if [[ ${#CC} -gt 0 || ${#MI} -gt 0 || ${#L} -gt 0 ]]; then
  exit 1
fi

