# Shared helpers for deploy.sh / teardown.sh (sourced, not executed).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
CDK="npx --yes aws-cdk@latest"

log()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required but not installed"; }

system_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
      echo "$candidate"; return
    fi
  done
  die "Python 3.11+ is required"
}

venv_python() {
  if [[ -x "$VENV/bin/python" ]]; then echo "$VENV/bin/python"; else echo "$VENV/Scripts/python"; fi
}

ensure_venv() {
  if [[ ! -d "$VENV" ]]; then
    log "Creating Python virtualenv"
    "$(system_python)" -m venv "$VENV"
  fi
  PY="$(venv_python)"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r "$ROOT/infra/requirements.txt"
  # the CDK CLI runs the app through the OS shell; on Windows (Git Bash) that needs a native path
  APP_CMD="$PY app.py"
  if command -v cygpath >/dev/null 2>&1; then APP_CMD="$(cygpath -w "$PY") app.py"; fi
  export PY APP_CMD
}

# Run the CDK CLI with credentials resolved by the AWS CLI (SSO, `aws login`, profiles...), so it sees
# the same identity even for providers the CLI's SDK doesn't support. Scoped to a subshell: long-running
# AWS CLI polling keeps using its own auto-refreshing provider.
cdk_run() {
  (
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
      eval "$(aws configure export-credentials --format env 2>/dev/null)" || true
    fi
    cd "$ROOT/infra" && $CDK "$@" --app "$APP_CMD"
  )
}

# config.yaml value by dotted path, e.g. cfg region / cfg bedrock.llm_model_id
cfg() {
  "$PY" - "$1" <<'PYEOF'
import sys, yaml, pathlib
value = yaml.safe_load(pathlib.Path("config.yaml").read_text())
local = pathlib.Path("config.local.yaml")
if local.exists():
    def merge(a, b):
        return {**a, **{k: merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v for k, v in b.items()}}
    value = merge(value, yaml.safe_load(local.read_text()) or {})
for part in sys.argv[1].split("."):
    value = value[part]
print(value)
PYEOF
}

# CloudFormation output of a stack
stack_output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" --output text
}
