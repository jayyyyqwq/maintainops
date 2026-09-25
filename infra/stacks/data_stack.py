"""Storage, alerting and cost guardrails shared by every other stack."""

from __future__ import annotations

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from constructs import Construct

from settings import ROOT, Settings


def private_bucket(scope: Construct, construct_id: str, **kwargs) -> s3.Bucket:
    return s3.Bucket(
        scope,
        construct_id,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        encryption=s3.BucketEncryption.S3_MANAGED,
        enforce_ssl=True,
        removal_policy=RemovalPolicy.DESTROY,
        auto_delete_objects=True,
        **kwargs,
    )


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, settings: Settings, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.data_bucket = private_bucket(
            self,
            "DataBucket",
            lifecycle_rules=[s3.LifecycleRule(prefix="runs/", expiration=Duration.days(90))],
        )
        s3deploy.BucketDeployment(
            self,
            "RawDataset",
            sources=[s3deploy.Source.asset(str(ROOT / "data"))],
            destination_bucket=self.data_bucket,
            destination_key_prefix="raw/",
            prune=False,
        )

        self.table = dynamodb.TableV2(
            self,
            "Table",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.alert_topic = sns.Topic(self, "AlertTopic", display_name="MaintainOps alerts", enforce_ssl=True)
        if settings.alert_email:
            self.alert_topic.add_subscription(subs.EmailSubscription(settings.alert_email))
            self._budget(settings)

        CfnOutput(self, "DataBucketName", value=self.data_bucket.bucket_name)
        CfnOutput(self, "TableName", value=self.table.table_name)

    def _budget(self, settings: Settings) -> None:
        subscriber = budgets.CfnBudget.SubscriberProperty(
            subscription_type="EMAIL", address=settings.alert_email
        )
        budgets.CfnBudget(
            self,
            "MonthlyBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name=f"{settings.project}-monthly",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=settings.budget_usd, unit="USD"),
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        notification_type=kind,
                        comparison_operator="GREATER_THAN",
                        threshold=threshold,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[subscriber],
                )
                for kind, threshold in (("ACTUAL", 80), ("FORECASTED", 100))
            ],
        )
