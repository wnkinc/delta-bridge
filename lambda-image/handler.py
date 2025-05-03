import json
import os
import uuid
import tempfile
import boto3
import pandas as pd
from deltalake.writer import write_deltalake
from datetime import datetime

# ---------------------------------------------------------------------------
# Env and clients
# ---------------------------------------------------------------------------

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb")
BUCKET = os.environ["BUCKET_NAME"]
DDB_TABLE_NAME = os.environ["DDB_TABLE_NAME"]

# ---------------------------------------------------------------------------
# Main Lambda entrypoint
# ---------------------------------------------------------------------------

def main(event, context):
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method")
        path = event.get("requestContext", {}).get("http", {}).get("path")

        # -------------------------------------------------------------------
        # /presign - generates upload URL and tracks dataset in DynamoDB
        # -------------------------------------------------------------------
        if method == "POST" and path == "/presign":
            body = json.loads(event.get("body", "{}"))
            user_id = body.get("userId")
            filename = body.get("filename", "upload.csv")

            if not user_id or not filename:
                return {
                    "statusCode": 400,
                    "body": json.dumps({ "error": "Missing userId or filename" })
                }

            table_id = uuid.uuid4().hex
            s3_key = f"datasets/{table_id}/raw/{filename}"

            # Save metadata to DynamoDB
            dynamodb.put_item(
                TableName=DDB_TABLE_NAME,
                Item={
                    "userId": { "S": user_id },
                    "fileKey": { "S": s3_key },
                    "tableId": { "S": table_id },
                    "filename": { "S": filename },
                    "status": { "S": "pending" },
                    "createdAt": { "S": datetime.utcnow().isoformat() }
                }
            )

            # Generate presigned URL
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

        # -------------------------------------------------------------------
        # /process - converts uploaded CSV to Delta format and stores result
        # -------------------------------------------------------------------
        if method == "POST" and path == "/process":
            body = json.loads(event.get("body", "{}"))
            s3_key = body.get("s3_key")
            table_id = s3_key.split("/")[1] if s3_key else None

            if not s3_key or not table_id:
                return {
                    "statusCode": 400,
                    "body": json.dumps({ "error": "Missing or invalid s3_key" })
                }

            local_csv = f"/tmp/{uuid.uuid4().hex}.csv"
            s3.download_file(BUCKET, s3_key, local_csv)

            df = pd.read_csv(local_csv)

            delta_dir = f"/tmp/{uuid.uuid4().hex}"
            write_deltalake(delta_dir, df, mode="overwrite")

            for root, _, files in os.walk(delta_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, delta_dir)
                    out_key = f"datasets/{table_id}/delta/{rel_path}"
                    s3.upload_file(full_path, BUCKET, out_key)

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Delta written",
                    "table_id": table_id
                })
            }

        # -------------------------------------------------------------------
        # Catch-all: unknown route
        # -------------------------------------------------------------------
        return {
            "statusCode": 404,
            "body": json.dumps({ "error": "Route not found" })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({ "error": str(e) })
        }
