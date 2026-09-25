"""Shared factory so every Lambda gets the same runtime, packaging and log retention."""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from settings import ROOT

LAMBDA_SOURCE = str(ROOT / "lambdas")
EXCLUDE = ["**/__pycache__", "**/*.pyc"]


def python_function(
    scope: Construct,
    construct_id: str,
    *,
    handler: str,
    environment: dict[str, str] | None = None,
    timeout_seconds: int = 30,
    memory_mb: int = 256,
    description: str = "",
) -> lambda_.Function:
    """Python 3.12 on arm64 (cheaper per ms); code = lambdas/ (boto3 only, no bundling)."""
    log_group = logs.LogGroup(
        scope,
        f"{construct_id}Logs",
        retention=logs.RetentionDays.TWO_WEEKS,
        removal_policy=RemovalPolicy.DESTROY,
    )
    return lambda_.Function(
        scope,
        construct_id,
        runtime=lambda_.Runtime.PYTHON_3_12,
        architecture=lambda_.Architecture.ARM_64,
        code=lambda_.Code.from_asset(LAMBDA_SOURCE, exclude=EXCLUDE),
        handler=handler,
        environment=environment or {},
        timeout=Duration.seconds(timeout_seconds),
        memory_size=memory_mb,
        log_group=log_group,
        description=description,
    )
