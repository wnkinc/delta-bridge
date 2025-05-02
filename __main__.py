import pulumi
import pulumi_aws as aws
import pulumi_aws.apigatewayv2 as apigw
import pulumi_awsx as awsx

# 1) Create S3 bucket
bucket = aws.s3.Bucket("datasets")

# 2) IAM role for Lambda
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
    }"""
)

aws.iam.RolePolicyAttachment("lambda-basic-exec",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)

# 3) Grant S3 PutObject access
aws.iam.RolePolicy("lambda-s3-policy",
    role=lambda_role.id,
    policy=bucket.arn.apply(lambda arn: aws.iam.get_policy_document(
        statements=[{
            "effect": "Allow",
            "actions": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
            "resources": [
                f"{arn}",
                f"{arn}/*"
            ]
        }]
    ).json)
)

# 4) ECR repo
repo = awsx.ecr.Repository("ingest-repo")

# 5) Build and push Docker image
image = awsx.ecr.Image("ingest-image",
    repository_url=repo.url,
    context="lambda-image"
)

# 6) Lambda function using image
lambda_func = aws.lambda_.Function("ingest-fn",
    package_type="Image",
    image_uri=image.image_uri,
    role=lambda_role.arn,
    architectures=["arm64"],
    timeout=20,
    memory_size=256,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "BUCKET_NAME": bucket.bucket
        }
    )
)

# 7) Create HTTP API
api = apigw.Api("ingest-api",
    protocol_type="HTTP"
)

integration = apigw.Integration("lambda-integration",
    api_id=api.id,
    integration_type="AWS_PROXY",
    integration_uri=lambda_func.invoke_arn,
    integration_method="POST",
    payload_format_version="2.0"
)

# Register both /presign and /process routes
apigw.Route("post-presign-route",
    api_id=api.id,
    route_key="POST /presign",
    target=integration.id.apply(lambda iid: f"integrations/{iid}")
)

apigw.Route("post-process-route",
    api_id=api.id,
    route_key="POST /process",
    target=integration.id.apply(lambda iid: f"integrations/{iid}")
)

# Deploy API
apigw.Stage("api-stage",
    api_id=api.id,
    name="$default",
    auto_deploy=True
)

# 8) Permission for API Gateway to invoke Lambda
aws.lambda_.Permission("api-lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_func.name,
    principal="apigateway.amazonaws.com",
    source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*")
)

# 9) Export outputs
pulumi.export("bucket_name", bucket.id)
pulumi.export("api_url", api.api_endpoint)
