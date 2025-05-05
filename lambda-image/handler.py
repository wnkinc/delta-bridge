import json
import os
import uuid
import boto3
from datetime import datetime

# ---------------------------------------------------------------------------
# Environment and clients
# ---------------------------------------------------------------------------
BUCKET = os.environ["BUCKET_NAME"]
DDB_TABLE = os.environ["DDB_TABLE_NAME"]
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:3000")
DELTA_INSTANCE_ID = os.environ["DELTA_INSTANCE_ID"]

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb")
ssm = boto3.client("ssm")


# ---------------------------------------------------------------------------
# Helper: build standard HTTP responses
# ---------------------------------------------------------------------------
def build_response(status_code: int, body: dict):
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
# Process S3 object to Delta and update status in DynamoDB
# ---------------------------------------------------------------------------
def process_s3_object(bucket: str, key: str):
    import pandas as pd  # lazy import
    from deltalake.writer import write_deltalake  # lazy import
    import os

    parts = key.split("/")
    if len(parts) < 3:
        raise ValueError(f"Unexpected S3 key format: {key}")
    table_id = parts[1]

    local_csv = f"/tmp/{uuid.uuid4().hex}.csv"
    s3.download_file(bucket, key, local_csv)

    df = pd.read_csv(local_csv)
    delta_dir = f"/tmp/{uuid.uuid4().hex}"
    write_deltalake(delta_dir, df, mode="overwrite")

    for root, _, files in os.walk(delta_dir):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, delta_dir)
            out_key = f"datasets/{table_id}/delta/{rel_path}"
            s3.upload_file(full_path, bucket, out_key)

    # Update status in DynamoDB from 'pending' to 'converted'
    scan_resp = dynamodb.scan(
        TableName=DDB_TABLE,
        FilterExpression="fileKey = :fk",
        ExpressionAttributeValues={":fk": {"S": key}},
        ProjectionExpression="userId",
    )
    items = scan_resp.get("Items", [])
    if items:
        user_id = items[0]["userId"]["S"]
        dynamodb.update_item(
            TableName=DDB_TABLE,
            Key={
                "userId": {"S": user_id},
                "fileKey": {"S": key},
            },
            UpdateExpression="SET #s = :new",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":new": {"S": "converted"}},
        )


# ---------------------------------------------------------------------------
# Share via SSM: ensure share.yaml exists, append entry, restart service
# ---------------------------------------------------------------------------
def share_table(table_id: str):
    """
    Bootstraps share.yaml if needed, appends a new entry, and restarts the service.
    """
    script = f"""
mkdir -p /home/ubuntu/shares

if [ ! -f /home/ubuntu/shares/share.yaml ]; then
  echo "shareCredentialsVersion: 1" > /home/ubuntu/shares/share.yaml
  echo "shares:"                  >> /home/ubuntu/shares/share.yaml
fi

cat << 'EOF' >> /home/ubuntu/shares/share.yaml
  - name: {table_id}
    schema: default
    location: s3a://{BUCKET}/datasets/{table_id}/delta
EOF

sudo systemctl restart delta-sharing
"""
    resp = ssm.send_command(
        InstanceIds=[DELTA_INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [script]},
    )
    return resp["Command"]["CommandId"]


# ---------------------------------------------------------------------------
# Lambda entrypoint
# ---------------------------------------------------------------------------
def main(event, context):
    # 1) S3 Event trigger (auto conversion)
    if "Records" in event and event["Records"][0].get("eventSource") == "aws:s3":
        for record in event["Records"]:
            bucket_name = record["s3"]["bucket"]["name"]
            object_key = record["s3"]["object"]["key"]
            try:
                process_s3_object(bucket_name, object_key)
            except Exception as e:
                print(f"❌ process_s3_object failed: {e}")
                raise
        return {"statusCode": 200}

    # 2) HTTP API Gateway trigger
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method")
    path = http.get("path")

    # POST /presign
    if method == "POST" and path == "/presign":
        payload = json.loads(event.get("body", "{}") or "{}")
        user_id = payload.get("userId")
        filename = payload.get("filename")
        if not user_id or not filename:
            return build_response(400, {"error": "Missing userId or filename"})

        table_id = uuid.uuid4().hex
        s3_key = f"datasets/{table_id}/raw/{filename}"

        dynamodb.put_item(
            TableName=DDB_TABLE,
            Item={
                "userId": {"S": user_id},
                "fileKey": {"S": s3_key},
                "tableId": {"S": table_id},
                "filename": {"S": filename},
                "status": {"S": "pending"},
                "createdAt": {"S": datetime.utcnow().isoformat()},
            },
        )

        url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": BUCKET, "Key": s3_key, "ContentType": "text/csv"},
            ExpiresIn=3600,
        )
        return build_response(200, {"url": url, "tableId": table_id, "s3Key": s3_key})

    # POST /process (manual trigger)
    if method == "POST" and path == "/process":
        payload = json.loads(event.get("body", "{}") or "{}")
        s3_key = payload.get("s3Key") or payload.get("s3_key")
        if not s3_key:
            return build_response(400, {"error": "Missing s3Key"})
        try:
            process_s3_object(BUCKET, s3_key)
        except Exception as e:
            return build_response(500, {"error": str(e)})
        return build_response(200, {"message": "Delta table written", "s3Key": s3_key})

    # POST /share (new SSM-driven share)
    if method == "POST" and path == "/share":
        payload = json.loads(event.get("body", "{}") or "{}")
        table_id = payload.get("tableId")
        if not table_id:
            return build_response(400, {"error": "Missing tableId"})
        try:
            cmd_id = share_table(table_id)
        except Exception as e:
            return build_response(500, {"error": str(e)})
        snippet = {
            "profileFile": "share_creds.json",
            "tableUrl": f"share://my_share.default.{table_id}",
            "ssmCommandId": cmd_id,
        }
        return build_response(200, {"snippet": snippet})

    # GET /datasets — list user’s uploads
    if method == "GET" and path == "/datasets":
        params = event.get("queryStringParameters") or {}
        user_id = params.get("userId")
        if not user_id:
            return build_response(400, {"error": "Missing userId"})
        resp = dynamodb.query(
            TableName=DDB_TABLE,
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": {"S": user_id}},
        )
        items = [
            {
                "tableId": i["tableId"]["S"],
                "filename": i["filename"]["S"],
                "status": i["status"]["S"],
            }
            for i in resp.get("Items", [])
        ]
        return build_response(200, {"datasets": items})

    # Fallback
    return build_response(404, {"error": "Route not found"})
