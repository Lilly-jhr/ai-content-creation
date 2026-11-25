#!/usr/bin/env bash
# PreToolUse(Bash): block git add/commit that would stage secrets. Exit 2 = block with message.
input=$(cat)
cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
case "$cmd" in
  *"git add"*|*"git commit"*) ;;
  *) exit 0 ;;
esac
if printf '%s' "$cmd" | grep -Eq '(^|[ /])(\.env|kaggle\.json|[^ ]*\.key|[^ ]*\.pem)( |$)'; then
  echo "Blocked: refusing to stage a secrets file (.env / kaggle.json / *.key)." >&2
  exit 2
fi
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
staged=$(git diff --cached --name-only 2>/dev/null)
if printf '%s\n' "$staged" | grep -Eq '(^|/)(\.env|kaggle\.json)$'; then
  echo "Blocked: a secrets file is already staged. Unstage it: git restore --staged <file>" >&2
  exit 2
fi
if git diff --cached -U0 2>/dev/null | grep -Eq '^\+.*(AIza[0-9A-Za-z_-]{30,}|sk_[A-Za-z0-9]{20,}|"key":\s*"[0-9a-f]{32}")'; then
  echo "Blocked: staged changes contain something that looks like an API key." >&2
  exit 2
fi
exit 0
