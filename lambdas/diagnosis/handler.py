"""Diagnosis: ground an alert in the maintenance manuals via Bedrock Knowledge Base RAG."""

from __future__ import annotations

import logging
import os
import time
from pathlib import PurePosixPath

import boto3

from common.store import ALERTS_PK, alert_sk, now_iso, to_dynamo
from diagnosis.prompt import FAILURE_NAMES, NO_CONTEXT_MARKER, PROMPT_TEMPLATE, build_query

logger = logging.getLogger()
logger.setLevel(logging.INFO)

agent_runtime = boto3.client("bedrock-agent-runtime")
sns = boto3.client("sns")
table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "maintainops"))

SNIPPET_CHARS = 400


def model_arn() -> str:
    region = os.environ.get("AWS_REGION", "ap-south-1")
    return f"arn:aws:bedrock:{region}::foundation-model/{os.environ['LLM_MODEL_ID']}"


def retrieve_and_generate(query: str) -> dict:
    return agent_runtime.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": os.environ["KNOWLEDGE_BASE_ID"],
                "modelArn": model_arn(),
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {"numberOfResults": int(os.environ["RETRIEVAL_RESULTS"])}
                },
                "generationConfiguration": {
                    "promptTemplate": {"textPromptTemplate": PROMPT_TEMPLATE},
                    "inferenceConfig": {"textInferenceConfig": {"temperature": 0.1, "maxTokens": 900}},
                },
            },
        },
    )


def extract_citations(response: dict) -> list[dict]:
    """Deduplicate retrieved references into {source, snippet} pairs."""
    seen, citations = set(), []
    for citation in response.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            text = ref.get("content", {}).get("text", "").strip()
            key = (uri, text[:80])
            if not text or key in seen:
                continue
            seen.add(key)
            citations.append({"source": PurePosixPath(uri).name or "manual", "snippet": text[:SNIPPET_CHARS]})
    return citations


def handler(event: dict, _context: object) -> dict:
    reading, prediction = event["reading"], event["prediction"]
    machine_id = reading["machine_id"]
    started = time.perf_counter()

    response = retrieve_and_generate(build_query(reading, prediction))
    explanation = response["output"]["text"].strip()
    citations = extract_citations(response)
    grounded = bool(citations) and NO_CONTEXT_MARKER not in explanation

    ts = now_iso()
    alert = {
        "pk": ALERTS_PK,
        "sk": alert_sk(ts, machine_id),
        "alert_id": alert_sk(ts, machine_id),
        "ts": ts,
        "reading_ts": event["ts"],
        "machine_id": machine_id,
        "failure_type": prediction["failure_type"],
        "risk": prediction["risk"],
        "prediction": prediction,
        "reading": reading,
        "explanation": explanation,
        "citations": citations,
        "grounded": grounded,
        "model_id": os.environ["LLM_MODEL_ID"],
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }
    table.put_item(Item=to_dynamo(alert))

    failure = FAILURE_NAMES.get(prediction["failure_type"], prediction["failure_type"])
    sns.publish(
        TopicArn=os.environ["ALERT_TOPIC_ARN"],
        Subject=f"[MaintainOps] {machine_id}: {failure} risk {prediction['risk']:.0%}"[:100],
        Message=(
            f"Machine {machine_id} - predicted {failure} (risk {prediction['risk']:.0%}).\n\n"
            f"{explanation}\n\n"
            f"Sources: {', '.join(sorted({c['source'] for c in citations})) or 'none'}\n"
            f"Dashboard: {os.environ.get('DASHBOARD_URL', '')}"
        ),
    )
    logger.info("alert %s grounded=%s citations=%d", alert["alert_id"], grounded, len(citations))
    return {"alert_id": alert["alert_id"], "grounded": grounded}
