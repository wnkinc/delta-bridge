import pulumi
import pulumi_aws as aws
import pulumi_aws.apigatewayv2 as apigw
import pulumi_awsx as awsx

# ---------------------------------------------------------------------------
# 1) S3 bucket that stores raw uploads + Delta tables
# ---------------------------------------------------------------------------
bucket = aws.s3.Bucket(
    "datasets",
    cors_rules=[aws.s3.BucketCorsRuleArgs(
        allowed_methods=["PUT", "POST", "GET", "HEAD"],
        allowed_origins=["http://localhost:3000"],  # or ["*"] for all
        allowed_headers=["*"],
        expose_headers=["ETag"],
        max_age_seconds=3000,
    )],
)

# ---------------------------------------------------------------------------
# 2) IAM role for the Lambda container
# ---------------------------------------------------------------------------
lambda_role = aws.iam.Role(
    "lambda-role",
    assume_role_policy=aws.iam.get_policy_document(
        statements=[{
            "effect": "Allow",
            "principals": [{
                "type": "Service",
                "identifiers": ["lambda.amazonaws.com"],
            }],
            "actions": ["sts:AssumeRole"],
        }]
    ).json,
)

aws.iam.RolePolicyAttachment(
    "lambda-basic-exec",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)

# Lambda may PUT raw files and READ/WRITE its Delta table path
aws.iam.RolePolicy(
    "lambda-s3-policy",
    role=lambda_role.id,
    policy=bucket.arn.apply(
        lambda arn: aws.iam.get_policy_document(
            statements=[{
                "effect": "Allow",
                "actions": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
                "resources": [arn, f"{arn}/*"],
            }]
        ).json
    ),
)

# ---------------------------------------------------------------------------
# 3) DynamoDB table for user-based dataset tracking
# ---------------------------------------------------------------------------
ddb_table = aws.dynamodb.Table(
    "dataset-tracking",
    attributes=[
        {"name": "userId", "type": "S"},
        {"name": "fileKey", "type": "S"},
    ],
    hash_key="userId",
    range_key="fileKey",
    billing_mode="PAY_PER_REQUEST",
)

# ---------------------------------------------------------------------------
# 4) Extend Lambda IAM permissions to write to DynamoDB
# ---------------------------------------------------------------------------
aws.iam.RolePolicy(
    "lambda-ddb-policy",
    role=lambda_role.id,
    policy=ddb_table.arn.apply(
        lambda arn: aws.iam.get_policy_document(
            statements=[
                {
                    "effect": "Allow",
                    "actions": [
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:GetItem",
                        "dynamodb:Query"
                    ],
                    "resources": [arn]
                }
            ]
        ).json
    ),
)

# ---------------------------------------------------------------------------
# 5) Build and publish the Lambda container image
# ---------------------------------------------------------------------------
repo   = awsx.ecr.Repository("ingest-repo")
image  = awsx.ecr.Image(
    "ingest-image",
    repository_url=repo.url,
    context="lambda-image",          # ← directory with Dockerfile + handler
)

lambda_func = aws.lambda_.Function(
    "ingest-fn",
    package_type="Image",
    image_uri=image.image_uri,
    role=lambda_role.arn,
    architectures=["arm64"],
    timeout=20,
    memory_size=256,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "BUCKET_NAME": bucket.bucket,
            "DDB_TABLE_NAME": ddb_table.name,
        },
    ),
)

# ---------------------------------------------------------------------------
# 6) API Gateway (HTTP API) with /presign and /process routes
# ---------------------------------------------------------------------------
api = apigw.Api(
    "ingest-api",
    protocol_type="HTTP",
    cors_configuration=apigw.ApiCorsConfigurationArgs(
        allow_origins=["http://localhost:3000"],
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,  # or True if needed
    ),
)


integration = apigw.Integration(
    "lambda-integration",
    api_id=api.id,
    integration_type="AWS_PROXY",
    integration_uri=lambda_func.invoke_arn,
    integration_method="POST",
    payload_format_version="2.0",
)

for route in ("/presign", "/process"):
    apigw.Route(
        f"post-{route.strip('/')}-route",
        api_id=api.id,
        route_key=f"POST {route}",
        target=integration.id.apply(lambda iid: f"integrations/{iid}"),
    )

apigw.Stage(
    "api-stage",
    api_id=api.id,
    name="$default",
    auto_deploy=True,
)

aws.lambda_.Permission(
    "api-lambda-permission",
    action="lambda:InvokeFunction",
    function=lambda_func.name,
    principal="apigateway.amazonaws.com",
    source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*"),
)

# ---------------------------------------------------------------------------
# 7) Security group + EC2 instance (Delta‑Sharing server)
# ---------------------------------------------------------------------------
ec2_sg = aws.ec2.SecurityGroup(
    "delta-share-sg",
    description="Allow SSH (22) and Delta Sharing (8080)",
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp", from_port=22,   to_port=22,   cidr_blocks=["0.0.0.0/0"]
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp", from_port=8080, to_port=8080, cidr_blocks=["0.0.0.0/0"]
        ),
    ],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"]
    )],
)

ubuntu_ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["099720109477"],
    filters=[{"name": "name", "values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]}],
)

ec2_role = aws.iam.Role(
    "delta-share-ec2-role",
    assume_role_policy=aws.iam.get_policy_document(
        statements=[{
            "effect": "Allow",
            "principals": [{
                "type": "Service",
                "identifiers": ["ec2.amazonaws.com"],
            }],
            "actions": ["sts:AssumeRole"],
        }]
    ).json,
)

aws.iam.RolePolicy(
    "delta-share-ec2-s3-read",
    role=ec2_role.id,
    policy=bucket.arn.apply(
        lambda arn: aws.iam.get_policy_document(
            statements=[
                {"effect": "Allow", "actions": ["s3:ListBucket"], "resources": [arn]},
                {"effect": "Allow", "actions": ["s3:GetObject"], "resources": [f"{arn}/*"]},
            ]
        ).json
    ),
)

ec2_profile = aws.iam.InstanceProfile("delta-share-ec2-profile", role=ec2_role.name)

ec2_instance = aws.ec2.Instance(
    "delta-share-server",
    instance_type="t3.micro",
    ami=ubuntu_ami.id,
    key_name="viewer-frontend-key",
    vpc_security_group_ids=[ec2_sg.id],
    iam_instance_profile=ec2_profile.name,
    tags={"Name": "DeltaSharingServer"},
)

# ---------------------------------------------------------------------------
# 8) Stack outputs
# ---------------------------------------------------------------------------
pulumi.export("api_url",            api.api_endpoint)
pulumi.export("bucket_name",        bucket.id)
pulumi.export("ddb_table_name",     ddb_table.name)
pulumi.export("delta_instance_ip",  ec2_instance.public_ip)

# 9) S3 Gateway VPC Endpoint to eliminate cross-AZ S3 hops
# ---------------------------------------------------------------------------
# 9a) Lookup the VPC you’re using (default VPC, if you haven’t created your own)
default_vpc = aws.ec2.get_vpc(default=True)

# 9b) Find its “main” route table (this is what your default subnets use)
main_route_table = aws.ec2.get_route_table(
    filters=[
        { "name": "vpc-id",          "values": [ default_vpc.id ] },
        { "name": "association.main", "values": [ "true" ] },
    ]
)

# 9c) Create the gateway endpoint without the lookup
s3_endpoint = aws.ec2.VpcEndpoint(
    "s3GatewayEndpoint",
    vpc_id=default_vpc.id,
    service_name=f"com.amazonaws.{aws.config.region}.s3",  # direct S3 endpoint name
    route_table_ids=[ main_route_table.id ],
    vpc_endpoint_type="Gateway",
)

# (Optional) export for reference
pulumi.export("s3GatewayEndpointId", s3_endpoint.id)
