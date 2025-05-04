import pulumi
import pulumi_aws as aws
import pulumi_aws.apigatewayv2 as apigw


def create_api(lambda_func: aws.lambda_.Function) -> apigw.Api:
    api = apigw.Api(
        "ingest-api",
        protocol_type="HTTP",
        cors_configuration=apigw.ApiCorsConfigurationArgs(
            allow_origins=["http://localhost:3000"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            allow_credentials=True,
        ),
    )

    # Lambda integration for all routes
    integration = apigw.Integration(
        "lambda-integration",
        api_id=api.id,
        integration_type="AWS_PROXY",
        integration_uri=lambda_func.invoke_arn,
        integration_method="POST",
        payload_format_version="2.0",
    )

    # Routes
    for method, route in [("POST", "/presign"), ("POST", "/process"), ("GET", "/datasets")]:
        apigw.Route(
            f"route-{method.lower()}-{route.strip('/')}",
            api_id=api.id,
            route_key=f"{method} {route}",
            target=integration.id.apply(lambda iid: f"integrations/{iid}"),
        )

    # Stage
    apigw.Stage(
        "api-stage",
        api_id=api.id,
        name="$default",
        auto_deploy=True,
    )

    # Permission so API GW can invoke the Lambda
    aws.lambda_.Permission(
        "api-lambda-permission",
        action="lambda:InvokeFunction",
        function=lambda_func.name,
        principal="apigateway.amazonaws.com",
        source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*"),
    )

    # Export endpoint
    pulumi.export("api_url", api.api_endpoint)

    return api
