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

# 3) Grant S3 PutObject on datasets prefix
aws.iam.RolePolicy("lambda-s3-policy",
    role=lambda_role.id,
    policy=bucket.arn.apply(lambda arn: aws.iam.get_policy_document(
        statements=[{
            "effect":    "Allow",
            "actions":   ["s3:PutObject"],
            "resources": [
                f"{arn}/uploads/*",    # legacy handler uploads
                f"{arn}/datasets/*",   # new delta uploads
            ],
        }]
    ).json)
)


# 4) Create an ECR repository for our image
repo = awsx.ecr.Repository("ingest-repo")  # Pulumi will create aws.ecr.Repository + registry :contentReference[oaicite:0]{index=0}

# 5) Build & push container image to that repo
image = awsx.ecr.Image("ingest-image",
    repository_url=repo.url,   # required in Python :contentReference[oaicite:1]{index=1}
    context="lambda-image"
)

# 6) Create Lambda from the container image
lambda_func = aws.lambda_.Function("ingest-fn",
    package_type="Image",
    image_uri=image.image_uri,
    role=lambda_role.arn,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={ "BUCKET_NAME": bucket.bucket }
    )
)

# 7) HTTP API (API Gateway v2)
api = apigw.Api("ingest-api", protocol_type="HTTP")

integration = apigw.Integration("lambda-integration",
    api_id=api.id,
    integration_type="AWS_PROXY",
    integration_uri=lambda_func.invoke_arn,
    integration_method="POST",
    payload_format_version="2.0"
)

apigw.Route("post-datasets-route",
    api_id=api.id,
    route_key="POST /datasets",
    target=integration.id.apply(lambda iid: f"integrations/{iid}")
)

apigw.Stage("api-stage",
    api_id=api.id,
    name="$default",
    auto_deploy=True
)

aws.lambda_.Permission("api-lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_func.name,
    principal="apigateway.amazonaws.com",
    source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*")
)

# 8) Export outputs
pulumi.export("bucket_name", bucket.id)
pulumi.export("api_url", api.api_endpoint)
