import json
import os
import boto3
import uuid

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]

def main(event, context):
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method")
        path = event.get("requestContext", {}).get("http", {}).get("path")

        if method == "POST" and path == "/presign":
            table_id = uuid.uuid4().hex
            filename = "upload.csv"  # could also be client-specified in real apps
            s3_key = f"datasets/{table_id}/raw/{filename}"

            url = s3.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': BUCKET,
                    'Key': s3_key,
                    'ContentType': 'text/csv'
                },
                ExpiresIn=3600
            )

            return {
                "statusCode": 200,
                "headers": { "Content-Type": "application/json" },
                "body": json.dumps({
                    "upload_url": url,
                    "table_id": table_id,
                    "s3_key": s3_key
                })
            }

        return {
            "statusCode": 404,
            "body": json.dumps({ "error": "Route not found" })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({ "error": str(e) })
        }
