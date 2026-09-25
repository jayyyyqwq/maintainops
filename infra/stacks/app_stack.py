"""Runtime: simulator -> inference -> diagnosis, the dashboard API and the static site."""

from __future__ import annotations

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_sns as sns
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct

from settings import Settings
from stacks.functions import python_function
from stacks.web import ApiSite, StaticSite

READ_ROUTES = {
    "/api/machines": apigw.HttpMethod.GET,
    "/api/machines/{machineId}/readings": apigw.HttpMethod.GET,
    "/api/alerts": apigw.HttpMethod.GET,
    "/api/alerts/{alertId}": apigw.HttpMethod.GET,
}
ACTION_ROUTES = {
    "/api/machines/{machineId}/fault": apigw.HttpMethod.POST,
    "/api/simulator": apigw.HttpMethod.POST,
}
READ_RATE, READ_BURST = 20, 40


class AppStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        settings: Settings,
        data_bucket: s3.IBucket,
        table: dynamodb.ITableV2,
        alert_topic: sns.ITopic,
        knowledge_base_id: str,
        knowledge_base_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.settings = settings
        rt = settings.runtime
        base_env = {"TABLE_NAME": table.table_name, "MACHINE_COUNT": str(rt["machines"])}

        # ------------------------------------------------------------ diagnosis
        llm_arn = f"arn:aws:bedrock:{self.region}::foundation-model/{settings.bedrock['llm_model_id']}"
        diagnosis = python_function(
            self, "DiagnosisFn", handler="diagnosis.handler.handler", timeout_seconds=90, memory_mb=256,
            environment=base_env | {
                "KNOWLEDGE_BASE_ID": knowledge_base_id,
                "LLM_MODEL_ID": settings.bedrock["llm_model_id"],
                "RETRIEVAL_RESULTS": str(settings.bedrock["retrieval_results"]),
                "ALERT_TOPIC_ARN": alert_topic.topic_arn,
            },
            description="Bedrock RetrieveAndGenerate over maintenance manuals",
        )
        diagnosis.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:RetrieveAndGenerate", "bedrock:Retrieve"], resources=[knowledge_base_arn],
        ))
        diagnosis.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:RetrieveAndGenerate"], resources=["*"],  # API-level check has no resource
        ))
        diagnosis.add_to_role_policy(iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=[llm_arn]))
        table.grant_write_data(diagnosis)
        alert_topic.grant_publish(diagnosis)

        # ------------------------------------------------------------ inference
        inference = python_function(
            self, "InferenceFn", handler="inference.handler.handler", timeout_seconds=60,
            environment=base_env | {
                "ENDPOINT_NAME": settings.endpoint_name,
                "DIAGNOSIS_FUNCTION": diagnosis.function_name,
                "RISK_THRESHOLD": str(rt["risk_threshold"]),
                "ALERT_COOLDOWN_SECONDS": str(rt["alert_cooldown_seconds"]),
                "READING_TTL_DAYS": str(rt["reading_ttl_days"]),
            },
            description="Scores readings on the SageMaker serverless endpoint",
        )
        inference.add_to_role_policy(iam.PolicyStatement(
            actions=["sagemaker:InvokeEndpoint"],
            resources=[f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/{settings.endpoint_name}"],
        ))
        table.grant_write_data(inference)
        diagnosis.grant_invoke(inference)

        # ------------------------------------------------------------ simulator
        simulator = python_function(
            self, "SimulatorFn", handler="simulator.handler.handler", timeout_seconds=30,
            environment=base_env | {
                "DATA_BUCKET": data_bucket.bucket_name,
                "INFERENCE_FUNCTION": inference.function_name,
            },
            description="Replays held-out AI4I rows as live sensor data",
        )
        data_bucket.grant_read(simulator, "replay/*")
        table.grant_read_write_data(simulator)
        inference.grant_invoke(simulator)

        schedule_role = iam.Role(
            self, "SchedulerRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com").with_conditions(
                {"StringEquals": {"aws:SourceAccount": self.account}}
            ),
        )
        simulator.grant_invoke(schedule_role)
        schedule = scheduler.CfnSchedule(
            self, "SimulatorSchedule",
            name=settings.schedule_name,
            description="MaintainOps sensor simulator tick (toggle from the dashboard)",
            schedule_expression=f"rate({rt['schedule_rate_minutes']} minute"
                                f"{'s' if rt['schedule_rate_minutes'] > 1 else ''})",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
            state="DISABLED",
            target=scheduler.CfnSchedule.TargetProperty(
                arn=simulator.function_arn, role_arn=schedule_role.role_arn, input="{}",
                retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(maximum_retry_attempts=0),
            ),
        )
        schedule_arn = f"arn:aws:scheduler:{self.region}:{self.account}:schedule/default/{settings.schedule_name}"

        # ------------------------------------------------------------------ api
        api_env = base_env | {"SCHEDULE_NAME": schedule.name}
        read_fn = python_function(
            self, "ApiReadFn", handler="api.read.handler", environment=api_env,
            description="Dashboard read API (DynamoDB read-only)",
        )
        table.grant_read_data(read_fn)
        read_fn.add_to_role_policy(iam.PolicyStatement(actions=["scheduler:GetSchedule"], resources=[schedule_arn]))

        actions_fn = python_function(
            self, "ApiActionsFn", handler="api.actions.handler",
            environment=api_env | {"SIMULATOR_FUNCTION": simulator.function_name},
            description="Demo actions: inject fault, toggle simulator",
        )
        actions_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["dynamodb:UpdateItem"], resources=[table.table_arn],
            conditions={"ForAllValues:StringLike": {"dynamodb:LeadingKeys": ["MACHINE#*"]}},
        ))
        actions_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["scheduler:GetSchedule", "scheduler:UpdateSchedule"], resources=[schedule_arn],
        ))
        actions_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["iam:PassRole"], resources=[schedule_role.role_arn],
            conditions={"StringEquals": {"iam:PassedToService": "scheduler.amazonaws.com"}},
        ))
        simulator.grant_invoke(actions_fn)

        # ------------------------------------------------------------ frontend
        http_api = apigw.HttpApi(self, "HttpApi", api_name=f"{settings.project}-api", create_default_stage=False)
        extra_routes: list[apigw.HttpRoute] = []
        if settings.hosting == "cloudfront":
            site_url = StaticSite(self, "Site", api=http_api).url
        else:
            api_site = ApiSite(self, "Site", api=http_api)
            extra_routes, site_url = api_site.routes, api_site.url
        self._configure_api(http_api, read_fn, actions_fn, extra_routes)
        diagnosis.add_environment("DASHBOARD_URL", site_url)

        CfnOutput(self, "DashboardUrl", value=site_url)
        CfnOutput(self, "ApiUrl", value=http_api.api_endpoint)
        CfnOutput(self, "ScheduleName", value=settings.schedule_name)
        CfnOutput(self, "SimulatorFunction", value=simulator.function_name)

    def _configure_api(
        self,
        api: apigw.HttpApi,
        read_fn: lambda_.IFunction,
        actions_fn: lambda_.IFunction,
        extra_routes: list[apigw.HttpRoute],
    ) -> None:
        rt = self.settings.runtime
        read = HttpLambdaIntegration("ReadIntegration", read_fn)
        actions = HttpLambdaIntegration("ActionsIntegration", actions_fn)
        routes = list(extra_routes)
        for path, method in READ_ROUTES.items():
            routes += api.add_routes(path=path, methods=[method], integration=read)
        for path, method in ACTION_ROUTES.items():
            routes += api.add_routes(path=path, methods=[method], integration=actions)

        stage = apigw.HttpStage(
            self, "DefaultStage", http_api=api, stage_name="$default", auto_deploy=True,
            throttle=apigw.ThrottleSettings(rate_limit=READ_RATE, burst_limit=READ_BURST),
        )
        # tighter limits on the write-ish demo actions
        stage.node.default_child.add_property_override("RouteSettings", {
            f"{method.value} {path}": {
                "ThrottlingRateLimit": rt["api_rate_limit_rps"],
                "ThrottlingBurstLimit": rt["api_burst_limit"],
            }
            for path, method in ACTION_ROUTES.items()
        })
        for route in routes:
            stage.node.add_dependency(route)
