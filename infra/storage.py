import pulumi
import pulumi_aws as aws


def create_storage():
    # 1) S3 bucket that stores raw uploads + Delta tables
    bucket = aws.s3.Bucket(
        "datasets",
        cors_rules=[
            aws.s3.BucketCorsRuleArgs(
                allowed_methods=["PUT", "POST", "GET", "HEAD"],
                allowed_origins=["http://localhost:3000"],  # or ["*"] for all origins
                allowed_headers=["*"],
                expose_headers=["ETag"],
                max_age_seconds=3000,
            )
        ],
    )

    # 2) DynamoDB table for user-based dataset tracking
    ddb_table = aws.dynamodb.Table(
        "dataset-tracking",
        attributes=[
            {"name": "userId",  "type": "S"},
            {"name": "fileKey", "type": "S"},
        ],
        hash_key="userId",
        range_key="fileKey",
        billing_mode="PAY_PER_REQUEST",
    )

    return bucket, ddb_table


def configure_bucket_notification(
    bucket: aws.s3.Bucket,
    lambda_func: aws.lambda_.Function,
    lambda_permission: aws.lambda_.Permission,
):
    """
    Configure S3 to invoke the given Lambda only for raw CSV uploads.
    """
    aws.s3.BucketNotification(
        "datasets-notification",
        bucket=bucket.id,
        lambda_functions=[
            aws.s3.BucketNotificationLambdaFunctionArgs(
                lambda_function_arn=lambda_func.arn,
                events=["s3:ObjectCreated:Put"],
                # Only trigger on keys under 'datasets/.../raw/' ending in '.csv'
                filter_prefix="datasets/",
                filter_suffix=".csv",
            )
        ],
        opts=pulumi.ResourceOptions(depends_on=[lambda_permission]),
    )