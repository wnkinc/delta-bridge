import pulumi
import pulumi_aws as aws

# 1. Create an S3 bucket to store uploaded datasets
bucket = aws.s3.Bucket("datasets")

# 2. Create a role that allows Lambda to run
lambda_role = aws.iam.Role("lambda-role",
    assume_role_policy="""{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": { "Service": "lambda.amazonaws.com" },
          "Action": "sts:AssumeRole"
        }
      ]
    }""")

# 3. Attach basic execution permissions to that role (e.g., write logs)
aws.iam.RolePolicyAttachment("lambda-basic-exec",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")

# 4. Define a placeholder Lambda function (actual code lives in ./src/handler.py)
lambda_func = aws.lambda_.Function("ingest-fn",
    runtime="python3.9",
    handler="handler.main",
    role=lambda_role.arn,
    code=pulumi.AssetArchive({
        ".": pulumi.FileArchive("./src")  # zip the folder and upload it
    }),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "BUCKET_NAME": bucket.bucket
        }
    )
)

# 5. Export values so we can see them in the CLI
pulumi.export("bucket_name", bucket.id)
pulumi.export("lambda_name", lambda_func.name)


import pulumi_aws.apigatewayv2 as apigw

# 1. Create an HTTP API
api = apigw.Api("ingest-api",
    protocol_type="HTTP"
)

# 2. Set Lambda as the integration target
integration = apigw.Integration("lambda-integration",
    api_id=api.id,
    integration_type="AWS_PROXY",
    integration_uri=lambda_func.invoke_arn,
    integration_method="POST",
    payload_format_version="2.0"
)

# 3. Create a route for POST /datasets
route = apigw.Route("post-datasets-route",
    api_id=api.id,
    route_key="POST /datasets",
    target=integration.id.apply(lambda iid: f"integrations/{iid}")
)




# 4. Deploy the API
stage = apigw.Stage("api-stage",
    api_id=api.id,
    name="$default",
    auto_deploy=True
)

# 5. Grant API Gateway permission to invoke the Lambda
permission = aws.lambda_.Permission("api-lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_func.name,
    principal="apigateway.amazonaws.com",
    source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*")
)

# 6. Export the URL
pulumi.export("api_url", api.api_endpoint)

