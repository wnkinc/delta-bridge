import pulumi_aws as aws


def create_lambda_role(bucket, ddb_table):
    # 1) IAM role for the Lambda container
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

    # Basic execution permissions for Lambda
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

    # Extend Lambda IAM permissions to write to DynamoDB
    aws.iam.RolePolicy(
        "lambda-ddb-policy",
        role=lambda_role.id,
        policy=ddb_table.arn.apply(
            lambda arn: aws.iam.get_policy_document(
                statements=[{
                    "effect": "Allow",
                    "actions": [
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                    ],
                    "resources": [arn],
                }]
            ).json
        ),
    )

    return lambda_role


def create_ec2_role(bucket):
    # 2) IAM role for the EC2 (Delta Sharing server)
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

    # Permissions for EC2 to read from S3 bucket
    aws.iam.RolePolicy(
        "delta-share-ec2-s3-read",
        role=ec2_role.id,
        policy=bucket.arn.apply(
            lambda arn: aws.iam.get_policy_document(
                statements=[
                    {"effect": "Allow", "actions": ["s3:ListBucket"], "resources": [arn]},
                    {"effect": "Allow", "actions": ["s3:GetObject"],   "resources": [f"{arn}/*"]},
                ]
            ).json
        ),
    )

    # Instance profile for EC2
    ec2_profile = aws.iam.InstanceProfile(
        "delta-share-ec2-profile",
        role=ec2_role.name,
    )

    return ec2_role, ec2_profile
