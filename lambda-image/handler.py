import json
import os
import uuid
import boto3
from datetime import datetime

# ---------------------------------------------------------------------------
# Environment and clients
# ---------------------------------------------------------------------------
BUCKET = os.environ.get("BUCKET_NAME")
DDB_TABLE = os.environ.get("DDB_TABLE_NAME")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:3000")

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb")

# ---------------------------------------------------------------------------
# Helper: build standard HTTP responses
# ---------------------------------------------------------------------------
def build_response(status_code: int, body: dict):
    print(f"🔔 Responding {status_code} with {body}")
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body),
    }

# ---------------------------------------------------------------------------
# Process S3 object to Delta
# ---------------------------------------------------------------------------
def process_s3_object(bucket: str, key: str):
    print(f"🔄 process_s3_object called with bucket={bucket}, key={key}")
    import pandas as pd  # lazy import
    from deltalake.writer import write_deltalake  # lazy import
    
    parts = key.split("/")
    if len(parts) < 3:
        print(f"❌ Unexpected key format: {key}")
        raise ValueError(f"Unexpected S3 key format: {key}")
    table_id = parts[1]
    print(f"📂 Detected table_id={table_id}")

    local_csv = f"/tmp/{uuid.uuid4().hex}.csv"
    print(f"⬇ Downloading s3://{bucket}/{key} to {local_csv}")
    s3.download_file(bucket, key, local_csv)

    df = pd.read_csv(local_csv)
    delta_dir = f"/tmp/{uuid.uuid4().hex}"
    print(f"📝 Writing Delta to {delta_dir}")
    write_deltalake(delta_dir, df, mode="overwrite")

    for root, _, files in os.walk(delta_dir):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, delta_dir)
            out_key = f"datasets/{table_id}/delta/{rel_path}"
            print(f"⬆ Uploading {full_path} to s3://{bucket}/{out_key}")
            s3.upload_file(full_path, bucket, out_key)
    print(f"✅ process_s3_object completed for table_id={table_id}")

# ---------------------------------------------------------------------------
# Lambda entrypoint
# ---------------------------------------------------------------------------
def main(event, context):
    print("❗️ Raw event received:", json.dumps(event))

    # 1) S3 Event trigger
    if "Records" in event and event["Records"][0].get("eventSource") == "aws:s3":
        print(f"📥 S3 trigger detected with {len(event['Records'])} record(s)")
        for record in event["Records"]:
            bucket_name = record["s3"]["bucket"]["name"]
            object_key = record["s3"]["object"]["key"]
            print(f"   → Invoking process_s3_object for {bucket_name}/{object_key}")
            try:
                process_s3_object(bucket_name, object_key)
            except Exception as e:
                print(f"❌ Error processing S3 object: {e}")
        return {"statusCode": 200}

    # 2) HTTP API Gateway trigger
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method")
    path = http.get("path")
    print(f"🚧 HTTP trigger detected: method={method}, path={path}")

    # POST /presign
    if method == "POST" and path == "/presign":
        print("✉️ Handling /presign request")
        payload = json.loads(event.get("body", "{}") or "{}")
        user_id = payload.get("userId")
        filename = payload.get("filename")
        if not user_id or not filename:
            return build_response(400, {"error": "Missing userId or filename"})

        table_id = uuid.uuid4().hex
        s3_key = f"datasets/{table_id}/raw/{filename}"

        print(f"🗄️  Tracking in DynamoDB: {table_id}, key={s3_key}")
        dynamodb.put_item(
            TableName=DDB_TABLE,
            Item={
                "userId": {"S": user_id},
                "fileKey": {"S": s3_key},
                "tableId": {"S": table_id},
                "filename": {"S": filename},
                "status": {"S": "pending"},
                "createdAt": {"S": datetime.utcnow().isoformat()},
            }
        )

        url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": BUCKET, "Key": s3_key, "ContentType": "text/csv"},
            ExpiresIn=3600,
        )
        print(f"🔑 Generated presigned URL: {url}")

        return build_response(200, {"url": url, "tableId": table_id, "s3Key": s3_key})

    # POST /process (fallback if manually invoked)
    if method == "POST" and path == "/process":
        print("✏️ Handling /process request")
        payload = json.loads(event.get("body", "{}") or "{}")
        s3_key = payload.get("s3Key") or payload.get("s3_key")
        if not s3_key:
            return build_response(400, {"error": "Missing s3Key"})
        try:
            process_s3_object(BUCKET, s3_key)
        except Exception as e:
            print(f"❌ Error in /process: {e}")
            return build_response(500, {"error": str(e)})
        return build_response(200, {"message": "Delta table written", "s3Key": s3_key})

    # Fallback
    print("❓ No matching route, returning 404")
    return build_response(404, {"error": "Route not found"})