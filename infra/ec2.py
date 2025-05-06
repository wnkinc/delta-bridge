# infra/ec2.py

import pulumi_aws as aws


def create_ec2(ec2_profile):
    # 1) Lookup the latest Ubuntu 22.04 AMI
    ubuntu = aws.ec2.get_ami(
        most_recent=True,
        owners=["099720109477"],
        filters=[
            {
                "name": "name",
                "values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"],
            },
            {"name": "virtualization-type", "values": ["hvm"]},
        ],
    )

    # 2) Security group for SSH and Delta Sharing
    sec_group = aws.ec2.SecurityGroup(
        "delta-sharing-sg",
        description="Allow SSH and Delta Sharing",
        ingress=[
            {
                "protocol": "tcp",
                "from_port": 22,
                "to_port": 22,
                "cidr_blocks": ["0.0.0.0/0"],
            },
            {
                "protocol": "tcp",
                "from_port": 8080,
                "to_port": 8080,
                "cidr_blocks": ["0.0.0.0/0"],
            },
        ],
        egress=[
            {
                "protocol": "-1",
                "from_port": 0,
                "to_port": 0,
                "cidr_blocks": ["0.0.0.0/0"],
            },
        ],
    )

    # 3) EC2 Instance
    instance = aws.ec2.Instance(
        "delta-sharing-server",
        instance_type="t3.micro",
        ami=ubuntu.id,
        key_name="viewer-frontend-key",
        vpc_security_group_ids=[sec_group.id],
        iam_instance_profile=ec2_profile.name,
        tags={
            "Name": "delta-sharing-server",
            "SSMEnabled": "true",  # Optional: helps you target by tag later
        },
    )

    # Return the security group, AMI data, and the instance resource
    return sec_group, ubuntu, instance
