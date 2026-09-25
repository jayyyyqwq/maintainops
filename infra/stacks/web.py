"""Dashboard hosting. Either way the site and /api/* share one origin, so no CORS is needed."""

from __future__ import annotations

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct

from settings import ROOT
from stacks.data_stack import private_bucket
from stacks.functions import python_function

DIST = ROOT / "frontend" / "dist"
PLACEHOLDER = ROOT / "infra" / "placeholder_site"


class StaticSite(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, api: apigw.HttpApi) -> None:
        super().__init__(scope, construct_id)
        bucket = private_bucket(self, "SiteBucket")
        region = Stack.of(self).region
        api_domain = f"{api.api_id}.execute-api.{region}.amazonaws.com"

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment="MaintainOps dashboard",
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_200,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(api_domain),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
            error_responses=[
                cloudfront.ErrorResponse(http_status=404, response_http_status=200,
                                         response_page_path="/index.html", ttl=Duration.seconds(0)),
            ],
        )

        source = DIST if (DIST / "index.html").exists() else PLACEHOLDER
        s3deploy.BucketDeployment(
            self,
            "Deploy",
            sources=[s3deploy.Source.asset(str(source))],
            destination_bucket=bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )
        self.url = f"https://{self.distribution.distribution_domain_name}"


class ApiSite(Construct):
    """Fallback hosting without CloudFront: a Lambda behind the same HTTP API serves the built
    dashboard from a private bucket. `/api/*` routes are more specific, so they still win."""

    def __init__(self, scope: Construct, construct_id: str, *, api: apigw.HttpApi) -> None:
        super().__init__(scope, construct_id)
        bucket = private_bucket(self, "SiteBucket")
        source = DIST if (DIST / "index.html").exists() else PLACEHOLDER
        s3deploy.BucketDeployment(
            self, "Deploy", sources=[s3deploy.Source.asset(str(source))], destination_bucket=bucket,
            memory_limit=512,
        )
        fn = python_function(
            self, "SiteFn", handler="webapp.handler.handler", memory_mb=256,
            environment={"SITE_BUCKET": bucket.bucket_name}, description="Serves the dashboard SPA",
        )
        bucket.grant_read(fn)
        integration = HttpLambdaIntegration("SiteIntegration", fn)
        self.routes = [
            *api.add_routes(path="/", methods=[apigw.HttpMethod.GET], integration=integration),
            *api.add_routes(path="/{proxy+}", methods=[apigw.HttpMethod.GET], integration=integration),
        ]
        self.url = api.api_endpoint
