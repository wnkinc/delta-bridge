import os, uuid, json, base64, traceback
from io import BytesIO
import boto3
from requests_toolbelt.multipart import decoder
from deltalake import write_deltalake

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]

def main(event, context):
    try:
        body = base64.b64decode(event["body"])
        ctype = event["headers"].get("content-type") or event["headers"].get("Content-Type")
        if not ctype:
            raise ValueError("Missing Content-Type")

        mp = decoder.MultipartDecoder(body, ctype)
        for part in mp.parts:
            disp = part.headers.get(b"Content-Disposition", b"").decode()
            if "filename=" not in disp:
                continue

            filename = disp.split("filename=")[1].strip('"\'')
            data = part.content
            table_id = uuid.uuid4().hex
            raw_key = f"datasets/{table_id}/raw/{filename}"
            table_uri = f"s3://{BUCKET}/datasets/{table_id}"

            # upload raw
            s3.upload_fileobj(BytesIO(data), BUCKET, raw_key)
            # init delta table
            write_deltalake(table_uri, f"s3://{BUCKET}/{raw_key}", mode="overwrite")

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": f"Initialized Delta table at {table_uri}",
                    "table_id": table_id,
                    "table_uri": table_uri
                })
            }

        return {"statusCode":400,"body":json.dumps({"error":"No file part"})}

    except Exception as e:
        traceback.print_exc()
        return {"statusCode":500,"body":json.dumps({"error":str(e)})}
