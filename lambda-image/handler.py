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
DELTA_SERVER_URL = os.environ["DELTA_SERVER_URL"]

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb")
ssm = boto3.client("ssm")


# ---------------------------------------------------------------------------
# Helper: standard HTTP response
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
# Convert CSV → Delta & mark 'converted'
# ---------------------------------------------------------------------------
def process_s3_object(bucket: str, key: str):
    import pandas as pd
    from deltalake.writer import write_deltalake
    import os

    table_id = key.split("/")[1]
    local_csv = f"/tmp/{uuid.uuid4().hex}.csv"
    s3.download_file(bucket, key, local_csv)

    df = pd.read_csv(local_csv)
    delta_dir = f"/tmp/{uuid.uuid4().hex}"
    write_deltalake(delta_dir, df, mode="overwrite")

    # upload back
    for root, _, files in os.walk(delta_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, delta_dir)
            out = f"datasets/{table_id}/delta/{rel}"
            s3.upload_file(full, bucket, out)

    # mark converted
    resp = dynamodb.scan(
        TableName=DDB_TABLE,
        FilterExpression="fileKey = :fk",
        ExpressionAttributeValues={":fk": {"S": key}},
        ProjectionExpression="userId",
    )
    for item in resp.get("Items", []):
        dynamodb.update_item(
            TableName=DDB_TABLE,
            Key={
                "userId": {"S": item["userId"]["S"]},
                "fileKey": {"S": key},
            },
            UpdateExpression="SET #s = :c",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": {"S": "converted"}},
        )


# ---------------------------------------------------------------------------
# Re-generate share.yaml with *all* shared tables
# ---------------------------------------------------------------------------
def share_table():
    # 1) fetch all shared tableIds
    resp = dynamodb.scan(
        TableName=DDB_TABLE,
        FilterExpression="#s = :sh",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":sh": {"S": "shared"}},
        ProjectionExpression="tableId",
    )
    table_ids = [i["tableId"]["S"] for i in resp.get("Items", [])]

    # 2) build YAML content
    lines = [
        "version: 1",
        "",
        "# server config",
        'host: "0.0.0.0"',
        "port: 8080",
        'endpoint: "/"',
        "",
        "shares:",
        "  - name: my_share",
        "    schemas:",
        "      - name: default",
        "        tables:",
    ]
    for tid in table_ids:
        lines.append(f"          - name: {tid}")
        lines.append(f"            location: s3a://{BUCKET}/datasets/{tid}/delta")
    yaml_body = "\n".join(lines)

    # 3) send to instance (overwrites file)
    script = f"""cat << 'EOF' > /home/ubuntu/shares/share.yaml
{yaml_body}
EOF

sudo systemctl restart delta-sharing
"""
    cmd = ssm.send_command(
        InstanceIds=[DELTA_INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [script]},
    )
    return cmd["Command"]["CommandId"]


# ---------------------------------------------------------------------------
# Lambda entrypoint
# ---------------------------------------------------------------------------
def main(event, context):
    # 1) S3-triggered conversion
    if "Records" in event and event["Records"][0].get("eventSource") == "aws:s3":
        for r in event["Records"]:
            process_s3_object(r["s3"]["bucket"]["name"], r["s3"]["object"]["key"])
        return {"statusCode": 200}

    # 2) HTTP routes
    http = event.get("requestContext", {}).get("http", {})
    method, path = http.get("method"), http.get("path")

    # POST /presign
    if method == "POST" and path == "/presign":
        body = json.loads(event.get("body", "{}") or "{}")
        user_id = body.get("userId")
        filename = body.get("filename")
        if not user_id or not filename:
            return build_response(400, {"error": "Missing userId or filename"})

        table_id = uuid.uuid4().hex
        s3_key = f"datasets/{table_id}/raw/{filename}"

        # record pending
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

    # POST /process
    if method == "POST" and path == "/process":
        body = json.loads(event.get("body", "{}") or "{}")
        key = body.get("s3Key") or body.get("s3_key")
        if not key:
            return build_response(400, {"error": "Missing s3Key"})
        process_s3_object(BUCKET, key)
        return build_response(200, {"message": "Delta table written", "s3Key": key})

    # POST /share
    if method == "POST" and path == "/share":
        body = json.loads(event.get("body", "{}") or "{}")
        table_id = body.get("tableId")
        if not table_id:
            return build_response(400, {"error": "Missing tableId"})

        # mark shared in DynamoDB
        scan = dynamodb.scan(
            TableName=DDB_TABLE,
            FilterExpression="tableId = :t",
            ExpressionAttributeValues={":t": {"S": table_id}},
            ProjectionExpression="userId,fileKey",
        )
        items = scan.get("Items", [])
        if not items:
            return build_response(404, {"error": "Dataset record not found"})
        user_id, file_key = items[0]["userId"]["S"], items[0]["fileKey"]["S"]

        dynamodb.update_item(
            TableName=DDB_TABLE,
            Key={"userId": {"S": user_id}, "fileKey": {"S": file_key}},
            UpdateExpression="SET #s = :sh",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":sh": {"S": "shared"}},
        )

        # regenerate share.yaml
        cmd_id = share_table()

        # build profile + snippet
        profile = {
            "shareCredentialsVersion": 1,
            "endpoint": DELTA_SERVER_URL,
            "bearerToken": "",
        }
        snippet_text = (
            "!pip install delta-sharing\n"
            "import json\n\n"
            "profile = " + json.dumps(profile, indent=2) + "\n\n"
            "with open('share_creds.json','w') as f:\n"
            "    json.dump(profile,f)\n\n"
            "import delta_sharing\n\n"
            f"df = delta_sharing.load_as_pandas('share_creds.json#my_share.default.{table_id}')\n"
            "df.head()\n"
        )

        # save snippet
        dynamodb.update_item(
            TableName=DDB_TABLE,
            Key={"userId": {"S": user_id}, "fileKey": {"S": file_key}},
            UpdateExpression="SET notebookSnippet = :ns",
            ExpressionAttributeValues={":ns": {"S": snippet_text}},
        )

        return build_response(
            200,
            {
                "profile": profile,
                "snippet": {
                    "tableUrl": f"share://my_share.default.{table_id}",
                    "notebookSnippet": snippet_text,
                },
                "status": "shared",
            },
        )

    # POST /unshare — revoke sharing of a table
    if method == "POST" and path == "/unshare":
        body = json.loads(event.get("body", "{}") or "{}")
        table_id = body.get("tableId")
        if not table_id:
            return build_response(400, {"error": "Missing tableId"})

        # 1) Find the record in DynamoDB
        resp = dynamodb.scan(
            TableName=DDB_TABLE,
            FilterExpression="tableId = :t",
            ExpressionAttributeValues={":t": {"S": table_id}},
            ProjectionExpression="userId,fileKey",
        )
        items = resp.get("Items", [])
        if not items:
            return build_response(404, {"error": "Dataset record not found"})
        user_id, file_key = items[0]["userId"]["S"], items[0]["fileKey"]["S"]

        # 2) Update status back to 'converted'
        dynamodb.update_item(
            TableName=DDB_TABLE,
            Key={"userId": {"S": user_id}, "fileKey": {"S": file_key}},
            UpdateExpression="SET #s = :c",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": {"S": "converted"}},
        )

        # 3) Regenerate share.yaml (will drop this table)
        share_table()

        # 4) Return success
        return build_response(200, {"status": "converted"})

    # GET /snippet — retrieve the saved notebook snippet for a table
    if method == "GET" and path == "/snippet":
        params = event.get("queryStringParameters") or {}
        table_id = params.get("tableId")
        if not table_id:
            return build_response(400, {"error": "Missing tableId"})

        # find the record (we scan because our primary key is userId+fileKey)
        resp = dynamodb.scan(
            TableName=DDB_TABLE,
            FilterExpression="tableId = :t",
            ExpressionAttributeValues={":t": {"S": table_id}},
            ProjectionExpression="notebookSnippet",
        )
        items = resp.get("Items", [])
        if not items or "notebookSnippet" not in items[0]:
            return build_response(404, {"error": "Snippet not found"})

        snippet = items[0]["notebookSnippet"]["S"]
        return build_response(200, {"notebookSnippet": snippet})

    # GET /datasets
    if method == "GET" and path == "/datasets":
        params = event.get("queryStringParameters") or {}
        user_id = params.get("userId")
        if not user_id:
            return build_response(400, {"error": "Missing userId"})
        resp = dynamodb.query(
            TableName=DDB_TABLE,
            KeyConditionExpression="userId = :u",
            ExpressionAttributeValues={":u": {"S": user_id}},
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

    return build_response(404, {"error": "Route not found"})
