import os
import json

def main(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Hello from your Pulumi Lambda!"})
    }
