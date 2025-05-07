# infra/web.py

import json, os, mimetypes
from pulumi import export, FileArchive, FileAsset
from pulumi_aws import s3, get_caller_identity

caller = get_caller_identity()
s3.AccountPublicAccessBlock(
    "accountPublicAccessBlock",
    account_id=caller.account_id,
    block_public_acls=False,
    block_public_policy=False,
    ignore_public_acls=False,
    restrict_public_buckets=False,
)

# 1) Create the S3 bucket for your sub-domain
site_bucket = s3.Bucket(
    "siteBucket",
    bucket="delta-bridge.bywk.dev",
    website=s3.BucketWebsiteArgs(
        index_document="index.html",
        error_document="index.html",
    ),
)

# 2) Ensure public policies aren’t blocked
s3.BucketPublicAccessBlock(
    "publicAccessBlock",
    bucket=site_bucket.id,
    block_public_acls=False,
    block_public_policy=False,
    ignore_public_acls=False,
    restrict_public_buckets=False,
)

# 3) Attach a bucket policy to allow public reads of objects
public_policy = site_bucket.id.apply(
    lambda bid: json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bid}/*"],
                }
            ],
        }
    )
)
s3.BucketPolicy(
    "bucketPolicy",
    bucket=site_bucket.id,
    policy=public_policy,
)

# 4) Walk the static-export directory and push each file
root_dir = "../web/out"
for dirpath, _, filenames in os.walk(root_dir):
    for fname in filenames:
        full_path = os.path.join(dirpath, fname)
        rel_path = os.path.relpath(full_path, root_dir).replace(os.sep, "/")
        content_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"

        s3.BucketObject(
            rel_path,  # Pulumi resource name (must be unique)
            bucket=site_bucket.id,  # your bucket
            key=rel_path,  # the S3 key (path in bucket)
            source=FileAsset(full_path),
            content_type=content_type,
        )

# 5) Export the S3 website endpoint for Cloudflare DNS
export("website_url", site_bucket.website_endpoint)
