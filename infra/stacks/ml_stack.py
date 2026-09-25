"""Training pipeline: Step Functions orchestrating SageMaker training, evaluation and deployment.

prepare -> spot training job -> model -> batch transform on test set -> quality gate
        -> serverless endpoint config -> create or update endpoint -> wait until InService
"""

from __future__ import annotations

from aws_cdk import CfnOutput, CustomResource, Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from aws_cdk import custom_resources as cr
from constructs import Construct

from settings import Settings
from stacks.functions import python_function

TAGS = [{"Key": "project", "Value": "maintainops"}]


class MlStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, settings: Settings, data_bucket: s3.IBucket, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.settings = settings
        sm = settings.sagemaker
        prefix = settings.project
        image = settings.xgboost_image()

        self.sagemaker_role = iam.Role(
            self,
            "SageMakerExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com").with_conditions(
                {"StringEquals": {"aws:SourceAccount": self.account}}
            ),
            description="Training, batch transform and serverless endpoint for MaintainOps",
        )
        data_bucket.grant_read_write(self.sagemaker_role)
        self.sagemaker_role.add_to_policy(iam.PolicyStatement(
            actions=["ecr:GetAuthorizationToken"], resources=["*"]
        ))
        self.sagemaker_role.add_to_policy(iam.PolicyStatement(
            actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"],
            resources=[f"arn:aws:ecr:{self.region}:{image.split('.')[0]}:repository/sagemaker-xgboost"],
        ))
        self.sagemaker_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                     "logs:DescribeLogStreams"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/*"],
        ))
        self.sagemaker_role.add_to_policy(iam.PolicyStatement(
            actions=["cloudwatch:PutMetricData"], resources=["*"],
            conditions={"StringLike": {"cloudwatch:namespace": ["/aws/sagemaker/*", "aws/sagemaker/*"]}},
        ))

        env = {"DATA_BUCKET": data_bucket.bucket_name}
        prepare_fn = python_function(
            self, "PrepareFn", handler="pipeline.prepare.handler", environment=env,
            timeout_seconds=120, memory_mb=1024, description="Feature engineering + stratified split",
        )
        data_bucket.grant_read_write(prepare_fn)
        evaluate_fn = python_function(
            self, "EvaluateFn", handler="pipeline.evaluate.handler", timeout_seconds=60, memory_mb=512,
            environment=env | {
                "RISK_THRESHOLD": str(settings.runtime["risk_threshold"]),
                "MIN_PR_AUC": str(settings.quality_gate["min_pr_auc"]),
                "MIN_RECALL": str(settings.quality_gate["min_recall"]),
                "MIN_PRECISION": str(settings.quality_gate.get("min_precision", 0)),
            },
            description="Quality gate on held-out test predictions",
        )
        data_bucket.grant_read_write(evaluate_fn)
        exists_fn = python_function(
            self, "EndpointExistsFn", handler="pipeline.endpoint.exists_handler",
            environment={"ENDPOINT_NAME": settings.endpoint_name},
        )
        exists_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["sagemaker:DescribeEndpoint"], resources=[self._arn("endpoint", settings.endpoint_name)]
        ))

        self.state_machine = sfn.StateMachine(
            self,
            "TrainingPipeline",
            state_machine_name=f"{prefix}-training",
            definition_body=sfn.DefinitionBody.from_chainable(
                self._definition(prepare_fn, evaluate_fn, exists_fn, image, sm)
            ),
            timeout=Duration.hours(2),
            tracing_enabled=False,
        )
        self._grant_sync_integrations()
        self._cleanup_on_delete()

        CfnOutput(self, "StateMachineArn", value=self.state_machine.state_machine_arn)

    # ---------------------------------------------------------------- helpers
    def _arn(self, resource: str, name: str) -> str:
        return f"arn:aws:sagemaker:{self.region}:{self.account}:{resource}/{name}"

    def _name(self, template: str = "{}") -> str:
        return sfn.JsonPath.format(f"{self.settings.project}-{template}", sfn.JsonPath.string_at("$.run_id"))

    def _sdk_call(self, construct_id: str, action: str, params: dict, resource: str | tuple[str, ...], **kwargs):
        """SDK integration scoped to project-prefixed ARNs of the given SageMaker resource type(s).
        CreateEndpoint/UpdateEndpoint are authorised against both the endpoint and the endpoint config."""
        types = (resource,) if isinstance(resource, str) else resource
        arns = [self._arn(t, f"{self.settings.project}-*") for t in types]
        return tasks.CallAwsService(
            self,
            construct_id,
            service="sagemaker",
            action=action,
            parameters=params,
            iam_resources=arns,
            additional_iam_statements=[iam.PolicyStatement(actions=["sagemaker:AddTags"], resources=arns)],
            **kwargs,
        )

    # ------------------------------------------------------------- definition
    def _definition(self, prepare_fn, evaluate_fn, exists_fn, image: str, sm: dict) -> sfn.IChainable:
        project = self.settings.project
        role_arn = self.sagemaker_role.role_arn
        hyperparameters = {k: str(v) for k, v in sm["hyperparameters"].items()} | {"csv_weights": "1"}

        init = sfn.Pass(self, "Init", parameters={"run_id": sfn.JsonPath.string_at("$$.Execution.Name")})
        prepare = tasks.LambdaInvoke(
            self, "PrepareData", lambda_function=prepare_fn,
            payload=sfn.TaskInput.from_object({"run_id": sfn.JsonPath.string_at("$.run_id")}),
            payload_response_only=True, result_path="$.prepare",
        )

        def channel(name: str, uri_path: str) -> dict:
            return {
                "ChannelName": name,
                "ContentType": "text/csv",
                "DataSource": {"S3DataSource": {
                    "S3DataType": "S3Prefix", "S3Uri.$": uri_path, "S3DataDistributionType": "FullyReplicated",
                }},
            }

        spot = bool(sm["use_spot_training"])
        stopping = {"MaxRuntimeInSeconds": 1800} | ({"MaxWaitTimeInSeconds": 3600} if spot else {})
        train = sfn.CustomState(self, "TrainXGBoost", state_json={
            "Type": "Task",
            "Resource": "arn:aws:states:::sagemaker:createTrainingJob.sync",
            "Parameters": {
                "TrainingJobName.$": f"States.Format('{project}-{{}}', $.run_id)",
                "AlgorithmSpecification": {"TrainingImage": image, "TrainingInputMode": "File"},
                "RoleArn": role_arn,
                "HyperParameters": hyperparameters,
                "InputDataConfig": [
                    channel("train", "$.prepare.train_uri"),
                    channel("validation", "$.prepare.validation_uri"),
                ],
                "OutputDataConfig": {"S3OutputPath.$": "$.prepare.model_output_uri"},
                "ResourceConfig": {
                    "InstanceCount": 1, "InstanceType": sm["training_instance_type"], "VolumeSizeInGB": 5,
                },
                "EnableManagedSpotTraining": spot,
                "StoppingCondition": stopping,
                "Tags": TAGS,
            },
            "ResultSelector": {
                "model_data.$": "$.ModelArtifacts.S3ModelArtifacts",
                "billable_seconds.$": "$.BillableTimeInSeconds",
            },
            "ResultPath": "$.training",
        })

        create_model = self._sdk_call("CreateModel", "createModel", {
            "ModelName": self._name(),
            "PrimaryContainer": {"Image": image, "ModelDataUrl": sfn.JsonPath.string_at("$.training.model_data")},
            "ExecutionRoleArn": role_arn,
            "Tags": TAGS,
        }, "model", result_path=sfn.JsonPath.DISCARD)
        create_model.add_retry(errors=["SageMaker.SageMakerException"], max_attempts=3)

        transform = sfn.CustomState(self, "BatchTransformTestSet", state_json={
            "Type": "Task",
            "Resource": "arn:aws:states:::sagemaker:createTransformJob.sync",
            "Parameters": {
                "TransformJobName.$": f"States.Format('{project}-{{}}', $.run_id)",
                "ModelName.$": f"States.Format('{project}-{{}}', $.run_id)",
                "TransformInput": {
                    "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri.$": "$.prepare.test_uri"}},
                    "ContentType": "text/csv",
                    "SplitType": "Line",
                },
                "TransformOutput": {
                    "S3OutputPath.$": "$.prepare.transform_output_uri",
                    "Accept": "text/csv",
                    "AssembleWith": "Line",
                },
                "TransformResources": {"InstanceType": sm["transform_instance_type"], "InstanceCount": 1},
                "Tags": TAGS,
            },
            # CDK drops None-valued keys, so keep a small result instead of discarding it
            "ResultSelector": {"transform_job.$": "$.TransformJobName"},
            "ResultPath": "$.transform",
        })

        evaluate = tasks.LambdaInvoke(
            self, "EvaluateModel", lambda_function=evaluate_fn,
            payload=sfn.TaskInput.from_object({"run_id": sfn.JsonPath.string_at("$.run_id")}),
            payload_response_only=True, result_path="$.evaluation",
        )

        endpoint_config = self._sdk_call("CreateServerlessEndpointConfig", "createEndpointConfig", {
            "EndpointConfigName": self._name(),
            "ProductionVariants": [{
                "VariantName": "AllTraffic",
                "ModelName": self._name(),
                "ServerlessConfig": {
                    "MemorySizeInMB": sm["serverless_memory_mb"],
                    "MaxConcurrency": sm["serverless_max_concurrency"],
                },
            }],
            "Tags": TAGS,
        }, "endpoint-config", result_path=sfn.JsonPath.DISCARD)

        exists = tasks.LambdaInvoke(
            self, "EndpointExists?", lambda_function=exists_fn,
            payload_response_only=True, result_path="$.endpoint",
        )
        endpoint_name = self.settings.endpoint_name
        create_endpoint = self._sdk_call("CreateEndpoint", "createEndpoint", {
            "EndpointName": endpoint_name, "EndpointConfigName": self._name(), "Tags": TAGS,
        }, ("endpoint", "endpoint-config"), result_path=sfn.JsonPath.DISCARD)
        update_endpoint = self._sdk_call("UpdateEndpoint", "updateEndpoint", {
            "EndpointName": endpoint_name, "EndpointConfigName": self._name(),
        }, ("endpoint", "endpoint-config"), result_path=sfn.JsonPath.DISCARD)

        wait = sfn.Wait(self, "WaitForEndpoint", time=sfn.WaitTime.duration(Duration.seconds(30)))
        describe = self._sdk_call("DescribeEndpoint", "describeEndpoint", {"EndpointName": endpoint_name},
                                  "endpoint", result_selector={"status.$": "$.EndpointStatus"},
                                  result_path="$.endpoint_status")
        done = sfn.Succeed(self, "EndpointInService")
        endpoint_failed = sfn.Fail(self, "EndpointFailed", error="EndpointFailed",
                                   cause="SageMaker endpoint entered Failed state")
        gate_failed = sfn.Fail(self, "QualityGateFailed", error="QualityGateFailed",
                               cause="Model metrics below config.yaml quality_gate; endpoint not updated")

        poll = wait.next(describe).next(
            sfn.Choice(self, "EndpointStatus?")
            .when(sfn.Condition.string_equals("$.endpoint_status.status", "InService"), done)
            .when(sfn.Condition.string_equals("$.endpoint_status.status", "Failed"), endpoint_failed)
            .otherwise(wait)
        )
        deploy = endpoint_config.next(exists).next(
            sfn.Choice(self, "CreateOrUpdate?")
            .when(sfn.Condition.boolean_equals("$.endpoint.exists", True), update_endpoint.next(poll))
            .otherwise(create_endpoint.next(poll))
        )
        return (
            init.next(prepare).next(train).next(create_model).next(transform).next(evaluate).next(
                sfn.Choice(self, "QualityGate")
                .when(sfn.Condition.boolean_equals("$.evaluation.passed", True), deploy)
                .otherwise(gate_failed)
            )
        )

    def _grant_sync_integrations(self) -> None:
        """Permissions for the .sync (run-a-job) service integrations, which CustomState can't infer."""
        project = self.settings.project
        self.state_machine.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob", "sagemaker:StopTrainingJob",
                "sagemaker:CreateTransformJob", "sagemaker:DescribeTransformJob", "sagemaker:StopTransformJob",
                "sagemaker:AddTags",
            ],
            resources=[self._arn("training-job", f"{project}-*"), self._arn("transform-job", f"{project}-*")],
        ))
        self.state_machine.add_to_role_policy(iam.PolicyStatement(
            actions=["sagemaker:ListTags"], resources=["*"],
        ))
        self.state_machine.add_to_role_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[self.sagemaker_role.role_arn],
            conditions={"StringEquals": {"iam:PassedToService": "sagemaker.amazonaws.com"}},
        ))
        self.state_machine.add_to_role_policy(iam.PolicyStatement(
            actions=["events:PutTargets", "events:PutRule", "events:DescribeRule"],
            resources=[
                f"arn:aws:events:{self.region}:{self.account}:rule/StepFunctionsGetEventsForSageMakerTrainingJobsRule",
                f"arn:aws:events:{self.region}:{self.account}:rule/StepFunctionsGetEventsForSageMakerTransformJobsRule",
            ],
        ))

    def _cleanup_on_delete(self) -> None:
        """The endpoint, configs and models are created by the pipeline, not CloudFormation;
        remove them when the stack is destroyed so nothing is left behind."""
        project = self.settings.project
        fn = python_function(
            self, "SageMakerCleanupFn", handler="pipeline.endpoint.cleanup_handler", timeout_seconds=900,
            environment={"ENDPOINT_NAME": self.settings.endpoint_name, "RESOURCE_PREFIX": f"{project}-"},
            description="Deletes pipeline-created SageMaker resources on stack delete",
        )
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["sagemaker:DescribeEndpoint", "sagemaker:DeleteEndpoint", "sagemaker:DeleteEndpointConfig",
                     "sagemaker:DeleteModel"],
            resources=[
                self._arn("endpoint", f"{project}-*"),
                self._arn("endpoint-config", f"{project}-*"),
                self._arn("model", f"{project}-*"),
            ],
        ))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["sagemaker:ListEndpointConfigs", "sagemaker:ListModels"], resources=["*"],
        ))
        provider = cr.Provider(self, "SageMakerCleanupProvider", on_event_handler=fn)
        CustomResource(self, "SageMakerCleanup", service_token=provider.service_token)
