"""Pipeline helpers for the SageMaker endpoint lifecycle.

`exists_handler`  - Step Functions branch: create vs update the serverless endpoint.
`cleanup_handler` - CloudFormation custom resource: on stack delete, remove the endpoint,
                    endpoint configs and models that the pipeline created outside CloudFormation.
"""

from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import ClientError

sagemaker = boto3.client("sagemaker")
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def endpoint_exists(name: str) -> bool:
    try:
        sagemaker.describe_endpoint(EndpointName=name)
    except ClientError as err:
        if err.response["Error"]["Code"] == "ValidationException":
            return False
        raise
    return True


def exists_handler(event: dict, _context: object) -> dict:
    return {"exists": endpoint_exists(os.environ["ENDPOINT_NAME"])}


def _delete_prefixed(prefix: str) -> None:
    for page in sagemaker.get_paginator("list_endpoint_configs").paginate(NameContains=prefix):
        for cfg in page["EndpointConfigs"]:
            logger.info("deleting endpoint config %s", cfg["EndpointConfigName"])
            sagemaker.delete_endpoint_config(EndpointConfigName=cfg["EndpointConfigName"])
    for page in sagemaker.get_paginator("list_models").paginate(NameContains=prefix):
        for model in page["Models"]:
            logger.info("deleting model %s", model["ModelName"])
            sagemaker.delete_model(ModelName=model["ModelName"])


def cleanup_handler(event: dict, _context: object) -> dict:
    if event["RequestType"] != "Delete":
        return {"PhysicalResourceId": "sagemaker-cleanup"}
    name = os.environ["ENDPOINT_NAME"]
    if endpoint_exists(name):
        logger.info("deleting endpoint %s", name)
        sagemaker.delete_endpoint(EndpointName=name)
        sagemaker.get_waiter("endpoint_deleted").wait(
            EndpointName=name, WaiterConfig={"Delay": 10, "MaxAttempts": 60}
        )
    _delete_prefixed(os.environ["RESOURCE_PREFIX"])
    return {"PhysicalResourceId": event.get("PhysicalResourceId", "sagemaker-cleanup")}
