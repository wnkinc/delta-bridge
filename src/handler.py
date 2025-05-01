import os
import uuid
import json
import boto3
import base64
import traceback
from io import BytesIO
from requests_toolbelt.multipart import decoder
from deltalake import write_deltalake

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]

def main(event, context):
    try:
        # 1. Decode body and figure out content-type
        body = base64.b64decode(event["body"])
        content_type = event["headers"].get("content-type") or event["headers"].get("Content-Type")
        if not content_type:
            raise ValueError("Missing Content-Type header")

        # 2. Parse multipart/form-data
        mp = decoder.MultipartDecoder(body, content_type)

        for part in mp.parts:
            disp = part.headers.get(b"Content-Disposition", b"").decode()
            if "filename=" not in disp:
                continue

            # 3. Extract filename and file bytes
            filename = disp.split("filename=")[1].strip('"\'')
            file_bytes = part.content

            # 4. Generate a unique table ID and S3 prefixes
            table_id = uuid.uuid4().hex
            raw_key = f"datasets/{table_id}/raw/{filename}"
            table_uri = f"s3://{BUCKET}/datasets/{table_id}"

            # 5. Upload the raw file to S3
            s3.upload_fileobj(
                Fileobj=BytesIO(file_bytes),
                Bucket=BUCKET,
                Key=raw_key
            )

            # 6. Initialize the Delta table (overwrite any existing)
            write_deltalake(
                table_uri,
                f"s3://{BUCKET}/{raw_key}",
                mode="overwrite"
            )

            # 7. Return success with the shareable path
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": f"Initialized Delta table at {table_uri}",
                    "table_id": table_id,
                    "table_uri": table_uri
                })
            }

        # No file part found?
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No file field in upload"})
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
