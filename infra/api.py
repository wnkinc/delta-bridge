import pulumi
import pulumi_aws as aws
import pulumi_aws.apigatewayv2 as apigw


def create_api(lambda_func: aws.lambda_.Function) -> apigw.Api:
    # 1) Define the HTTP API with CORS enabled for localhost and your Cloudflare domain
    api = apigw.Api(
        "ingest-api",
        protocol_type="HTTP",
        cors_configuration=apigw.ApiCorsConfigurationArgs(
            allow_origins=[
                "http://localhost:3000",  # local dev
                "https://delta-bridge.bywk.dev",  # production
            ],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            allow_credentials=True,
        ),
    )

    # 2) Wire up a Lambda proxy integration
    integration = apigw.Integration(
        "lambda-integration",
        api_id=api.id,
        integration_type="AWS_PROXY",
        integration_uri=lambda_func.invoke_arn,
        integration_method="POST",
        payload_format_version="2.0",
    )

    # 3) Create one route per endpoint
    for method, route in [
        ("POST", "/presign"),
        ("POST", "/process"),
        ("POST", "/share"),
        ("POST", "/unshare"),
        ("GET", "/datasets"),
        ("GET", "/snippet"),
    ]:
        apigw.Route(
            f"route-{method.lower()}-{route.strip('/')}",
            api_id=api.id,
            route_key=f"{method} {route}",
            target=integration.id.apply(lambda iid: f"integrations/{iid}"),
        )

    # 4) Deploy the default stage with auto-deploy on each change
    apigw.Stage(
        "api-stage",
        api_id=api.id,
        name="$default",
        auto_deploy=True,
    )

    # 5) Give API Gateway permission to invoke your Lambda
    aws.lambda_.Permission(
        "api-lambda-permission",
        action="lambda:InvokeFunction",
        function=lambda_func.name,
        principal="apigateway.amazonaws.com",
        source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*"),
    )

    # 6) Export the URL so you can reference it elsewhere
    pulumi.export("api_url", api.api_endpoint)

    return api
