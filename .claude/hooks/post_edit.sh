#!/usr/bin/env bash
# PostToolUse(Edit|Write): format Python files; validate storyboard.json. Fast and non-destructive.
input=$(cat)
file=$(printf '%s' "$input" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("file_path",""))' 2>/dev/null)
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
case "$file" in
  *.py)
    uv run --quiet ruff format --quiet "$file" >/dev/null 2>&1
    out=$(uv run --quiet ruff check "$file" 2>&1) || { echo "$out" >&2; exit 2; }
    ;;
  *storyboard.json)
    out=$(uv run --quiet python -m pipeline validate 2>&1) || { echo "$out" >&2; exit 2; }
    ;;
esac
exit 0
