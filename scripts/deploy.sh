#!/usr/bin/env bash
# One-command deploy: infrastructure, model training, knowledge-base ingestion.
#
#   ./scripts/deploy.sh             deploy; train only if no endpoint exists yet
#   ./scripts/deploy.sh --retrain   deploy and always run the training pipeline
#
# Works from AWS CloudShell or any machine with the AWS CLI configured (AWS_PROFILE is honoured).
# No Docker needed.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$ROOT"

RETRAIN=false
[[ "${1:-}" == "--retrain" ]] && RETRAIN=true

# ------------------------------------------------------------------ prerequisites
log "Checking prerequisites"
need aws; need node; need npm; need npx
ensure_venv
REGION="$(cfg region)"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" || die "AWS credentials not configured"
export CDK_DEFAULT_ACCOUNT="$ACCOUNT" CDK_DEFAULT_REGION="$REGION"
ok "account $ACCOUNT, region $REGION"

LLM="$(cfg bedrock.llm_model_id)"
EMBED="$(cfg bedrock.embedding_model_id)"
for model in "$LLM" "$EMBED"; do
  aws bedrock get-foundation-model --model-identifier "$model" --region "$REGION" >/dev/null 2>&1 \
    || die "Bedrock model $model is not available in $REGION (check config.yaml)"
done
ok "Bedrock models available: $LLM, $EMBED"

# ------------------------------------------------------------------------ frontend
log "Building dashboard"
(cd frontend && npm ci --no-audit --no-fund --silent && npm run build --silent)
ok "frontend/dist built"

# ------------------------------------------------------------------ infrastructure
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" >/dev/null 2>&1; then
  log "Bootstrapping CDK in $REGION"
  cdk_run bootstrap "aws://$ACCOUNT/$REGION"
fi
log "Deploying stacks (first run takes ~10 minutes: CloudFront is slow to create)"
cdk_run deploy --all --require-approval never --outputs-file ../cdk-outputs.json
ok "stacks deployed"

STATE_MACHINE="$(stack_output MaintainOps-ML StateMachineArn)"
KB_ID="$(stack_output MaintainOps-KnowledgeBase KnowledgeBaseId)"
DS_ID="$(stack_output MaintainOps-KnowledgeBase DataSourceId)"
DATA_BUCKET="$(stack_output MaintainOps-Data DataBucketName)"
DASHBOARD="$(stack_output MaintainOps-App DashboardUrl)"
ENDPOINT="$(cfg project)-xgb"

# ------------------------------------------------ knowledge base ingestion (async)
log "Starting knowledge-base ingestion"
INGESTION_ID="$(aws bedrock-agent start-ingestion-job --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
  --region "$REGION" --query ingestionJob.ingestionJobId --output text)"

# --------------------------------------------------------------- training pipeline
endpoint_status="$(aws sagemaker describe-endpoint --endpoint-name "$ENDPOINT" --region "$REGION" \
  --query EndpointStatus --output text 2>/dev/null || echo "Missing")"
if [[ "$RETRAIN" == true || "$endpoint_status" != "InService" ]]; then
  EXECUTION="train-$(date -u +%Y%m%d-%H%M%S)"
  log "Running training pipeline ($EXECUTION): prepare -> spot training -> evaluate -> serverless endpoint"
  EXEC_ARN="$(aws stepfunctions start-execution --state-machine-arn "$STATE_MACHINE" --name "$EXECUTION" \
    --region "$REGION" --query executionArn --output text)"
  while true; do
    status="$(aws stepfunctions describe-execution --execution-arn "$EXEC_ARN" --region "$REGION" \
      --query status --output text)"
    [[ "$status" != "RUNNING" ]] && break
    printf '    pipeline %s ... %s\n' "$status" "$(date +%H:%M:%S)"
    sleep 30
  done
  if [[ "$status" != "SUCCEEDED" ]]; then
    aws stepfunctions describe-execution --execution-arn "$EXEC_ARN" --region "$REGION" \
      --query '{error:error,cause:cause}' --output json >&2
    die "training pipeline $status"
  fi
  ok "model trained, evaluated and deployed to serverless endpoint $ENDPOINT"
else
  ok "endpoint $ENDPOINT already InService (use --retrain to retrain)"
fi

aws s3 cp "s3://$DATA_BUCKET/metrics/latest.json" "$ROOT/docs/metrics_sagemaker.json" --region "$REGION" \
  --only-show-errors && ok "SageMaker metrics saved to docs/metrics_sagemaker.json"

# ----------------------------------------------------------- wait for ingestion
while true; do
  status="$(aws bedrock-agent get-ingestion-job --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
    --ingestion-job-id "$INGESTION_ID" --region "$REGION" --query ingestionJob.status --output text)"
  [[ "$status" == "COMPLETE" || "$status" == "FAILED" || "$status" == "STOPPED" ]] && break
  sleep 10
done
[[ "$status" == "COMPLETE" ]] || die "knowledge-base ingestion $status"
ok "knowledge base indexed ($(aws bedrock-agent get-ingestion-job --knowledge-base-id "$KB_ID" \
  --data-source-id "$DS_ID" --ingestion-job-id "$INGESTION_ID" --region "$REGION" \
  --query ingestionJob.statistics.numberOfNewDocumentsIndexed --output text) new documents)"

# ------------------------------------------------------------------------- done
cat <<EOF

$(printf '\033[1;32m')MaintainOps is live.$(printf '\033[0m')

  Dashboard:  $DASHBOARD
  Simulator:  stopped (toggle it from the dashboard; it bills only while running)

  Next steps:
   1. Confirm the SNS subscription email sent to $(cfg alert_email) (also enables budget alerts).
   2. Open the dashboard, start the simulator, click "Inject fault" on any machine.
   3. When done: stop the simulator, or run ./scripts/teardown.sh to remove everything.
EOF
