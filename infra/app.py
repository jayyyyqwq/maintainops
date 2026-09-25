#!/usr/bin/env python3
"""MaintainOps CDK app. Region and model IDs come from config.yaml."""

from __future__ import annotations

import os

import aws_cdk as cdk

from settings import load_settings
from stacks.app_stack import AppStack
from stacks.data_stack import DataStack
from stacks.kb_stack import KnowledgeBaseStack
from stacks.ml_stack import MlStack


def build(app: cdk.App) -> cdk.App:
    settings = load_settings()
    env = cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=settings.region)
    prefix = "MaintainOps"

    data = DataStack(app, f"{prefix}-Data", settings=settings, env=env)
    MlStack(app, f"{prefix}-ML", settings=settings, data_bucket=data.data_bucket, env=env)
    kb = KnowledgeBaseStack(app, f"{prefix}-KnowledgeBase", settings=settings, env=env)
    AppStack(
        app,
        f"{prefix}-App",
        settings=settings,
        data_bucket=data.data_bucket,
        table=data.table,
        alert_topic=data.alert_topic,
        knowledge_base_id=kb.knowledge_base_id,
        knowledge_base_arn=kb.knowledge_base_arn,
        env=env,
    )
    cdk.Tags.of(app).add("project", settings.project)
    return app


if __name__ == "__main__":
    build(cdk.App()).synth()
