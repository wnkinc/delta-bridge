import pulumi_aws as aws
import pulumi_awsx as awsx
import os


def create_lambda(lambda_role, bucket, ddb_table, delta_instance_id):
    """
    Build and publish the Lambda container image, inject DELTA_INSTANCE_ID,
    and grant S3 invoke permissions.
    Returns:
      - repo: AWSX ECR repository
      - image: built image
      - lambda_func: Lambda Function resource
      - allow_s3_invoker: Lambda permission resource for S3 invocation
    """
    # 1) ECR repository and image
    repo = awsx.ecr.Repository("ingest-repo")
    image = awsx.ecr.Image(
        "ingest-image",
        repository_url=repo.url,
        context=os.path.join(os.path.dirname(__file__), "..", "lambda-image"),
    )

    # 2) Lambda function for ingesting/processing data
    lambda_func = aws.lambda_.Function(
        "ingest-fn",
        package_type="Image",
        image_uri=image.image_uri,
        role=lambda_role.arn,
        architectures=["arm64"],
        timeout=60,
        memory_size=512,
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables={
                "BUCKET_NAME": bucket.bucket,
                "DDB_TABLE_NAME": ddb_table.name,
                "DELTA_INSTANCE_ID": delta_instance_id,
            },
        ),
    )

    # 3) Permission to allow S3 to invoke this Lambda
    allow_s3_invoker = aws.lambda_.Permission(
        "allow-s3-invoke",
        action="lambda:InvokeFunction",
        function=lambda_func.name,
        principal="s3.amazonaws.com",
        source_arn=bucket.arn,
    )

    return repo, image, lambda_func, allow_s3_invoker


def create_ec2(ec2_profile):
    """
    Create security group and EC2 instance for Delta Sharing server.
    """
    # Security group allowing SSH and Delta Sharing port
    ec2_sg = aws.ec2.SecurityGroup(
        "delta-share-sg",
        description="Allow SSH (22) and Delta Sharing (8080)",
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp", from_port=22, to_port=22, cidr_blocks=["0.0.0.0/0"]
            ),
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp", from_port=8080, to_port=8080, cidr_blocks=["0.0.0.0/0"]
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"]
            )
        ],
    )

    # Latest Ubuntu 22.04 AMI lookup
    ubuntu_ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["099720109477"],
        filters=[
            {
                "name": "name",
                "values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"],
            }
        ],
    )

    # EC2 instance for Delta Sharing server
    ec2_instance = aws.ec2.Instance(
        "delta-share-server",
        instance_type="t3.micro",
        ami=ubuntu_ami.id,
        key_name="viewer-frontend-key",
        vpc_security_group_ids=[ec2_sg.id],
        iam_instance_profile=ec2_profile.name,
        tags={"Name": "DeltaSharingServer"},
    )

    return ec2_sg, ubuntu_ami, ec2_instance
