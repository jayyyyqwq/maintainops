#!/usr/bin/env bash
# Remove every MaintainOps resource: stacks, the pipeline-created SageMaker endpoint/configs/models
# (deleted by a custom resource during stack deletion), buckets and vectors.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$ROOT"

need aws; need npx
ensure_venv
REGION="$(cfg region)"
PROJECT="$(cfg project)"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" || die "AWS credentials not configured"
export CDK_DEFAULT_ACCOUNT="$ACCOUNT" CDK_DEFAULT_REGION="$REGION"

log "Stopping simulator"
if aws scheduler get-schedule --name "$PROJECT-simulator" --region "$REGION" >/dev/null 2>&1; then
  aws scheduler get-schedule --name "$PROJECT-simulator" --region "$REGION" --output json \
    | "$PY" -c 'import json,sys; s=json.load(sys.stdin); print(json.dumps({k:s[k] for k in ("Name","ScheduleExpression","FlexibleTimeWindow","Target") if k in s}))' \
    > .schedule.json
  aws scheduler update-schedule --cli-input-json file://.schedule.json --state DISABLED \
    --region "$REGION" >/dev/null && ok "simulator disabled"
  rm -f .schedule.json
fi

log "Destroying stacks (the SageMaker endpoint is deleted first by a custom resource)"
cdk_run destroy --all --force

log "Removing SageMaker log groups"
for group in "/aws/sagemaker/Endpoints/$PROJECT-xgb"; do
  aws logs delete-log-group --log-group-name "$group" --region "$REGION" 2>/dev/null && ok "deleted $group" || true
done

remaining="$(aws sagemaker list-endpoints --name-contains "$PROJECT" --region "$REGION" \
  --query 'length(Endpoints)' --output text)"
[[ "$remaining" == "0" ]] || die "$remaining SageMaker endpoint(s) still exist — check the console"
ok "no SageMaker endpoints left; MaintainOps removed"
echo "  The CDK bootstrap stack (CDKToolkit) is kept; delete it manually if you no longer use CDK."
