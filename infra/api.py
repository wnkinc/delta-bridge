import pulumi_aws.apigatewayv2 as apigw
import pulumi_aws as aws


def create_api(lambda_func):
    # 6) API Gateway (HTTP API) with /presign and /process routes
    api = apigw.Api(
        "ingest-api",
        protocol_type="HTTP",
        cors_configuration=apigw.ApiCorsConfigurationArgs(
            allow_origins=["http://localhost:3000"],
            allow_methods=["POST", "OPTIONS"],
            allow_headers=["*"],
            allow_credentials=False,
        ),
    )

    # Integration of Lambda with HTTP API
    integration = apigw.Integration(
        "lambda-integration",
        api_id=api.id,
        integration_type="AWS_PROXY",
        integration_uri=lambda_func.invoke_arn,
        integration_method="POST",
        payload_format_version="2.0",
    )

    # Routes for /presign and /process
    for route in ("/presign", "/process"):
        apigw.Route(
            f"post-{route.strip('/')}-route",
            api_id=api.id,
            route_key=f"POST {route}",
            target=integration.id.apply(lambda iid: f"integrations/{iid}"),
        )

    # Default stage deployment
    apigw.Stage(
        "api-stage",
        api_id=api.id,
        name="$default",
        auto_deploy=True,
    )

    # Permission for API Gateway to invoke Lambda
    aws.lambda_.Permission(
        "api-lambda-permission",
        action="lambda:InvokeFunction",
        function=lambda_func.name,
        principal="apigateway.amazonaws.com",
        source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*"),
    )

    return api
