# infra/__main__.py

import pulumi
import web  # ← pull in infra/web.py to provision your static site
from storage import create_storage, configure_bucket_notification
from iam import create_lambda_role, create_ec2_role
from compute import create_lambda
from ec2 import create_ec2
from api import create_api
from network import setup_network

# ---------------------------------------------------------------------------
# 1) STORAGE
# ---------------------------------------------------------------------------
bucket, ddb_table = create_storage()

# ---------------------------------------------------------------------------
# 2) IAM
# ---------------------------------------------------------------------------
(lambda_role,) = (create_lambda_role(bucket, ddb_table),)
ec2_role, ec2_profile = create_ec2_role(bucket)

# ---------------------------------------------------------------------------
# 3) COMPUTE
#    a) Spin up your EC2 first
ec2_sg, ubuntu_ami, ec2_instance = create_ec2(ec2_profile)

#    b) Then build the Lambda, passing in the EC2 instance ID
repo, image, lambda_func, allow_s3_invoker = create_lambda(
    lambda_role,
    bucket,
    ddb_table,
    ec2_instance.id,
    ec2_instance.public_ip,
)

# ---------------------------------------------------------------------------
# 4) API
# ---------------------------------------------------------------------------
api = create_api(lambda_func)

# ---------------------------------------------------------------------------
# 5) BUCKET NOTIFICATIONS
# ---------------------------------------------------------------------------
configure_bucket_notification(bucket, lambda_func, allow_s3_invoker)

# ---------------------------------------------------------------------------
# 6) NETWORK
# ---------------------------------------------------------------------------
vpc, rt, s3_endpoint = setup_network()

# ---------------------------------------------------------------------------
# 7) EXPORTS (your backend resources)
# ---------------------------------------------------------------------------
pulumi.export("api_url", api.api_endpoint)
pulumi.export("bucket_name", bucket.id)
pulumi.export("ddb_table_name", ddb_table.name)
pulumi.export("delta_instance_ip", ec2_instance.public_ip)
pulumi.export("delta_instance_id", ec2_instance.id)
pulumi.export("s3_gateway_endpoint_id", s3_endpoint.id)
pulumi.export("delta_sg_id", ec2_sg.id)

# (The `web.py` module itself already does:)
#    export("website_url", site_bucket.website_endpoint)
#    export("cdn_url", cdn.domain_name)
