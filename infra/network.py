import pulumi_aws as aws


def setup_network():
    # 1) Lookup the VPC (default or specify your own)
    default_vpc = aws.ec2.get_vpc(default=True)

    # 2) Find its main route table (used by default subnets)
    main_route_table = aws.ec2.get_route_table(
        filters=[
            {"name": "vpc-id",           "values": [default_vpc.id]},
            {"name": "association.main", "values": ["true"]},
        ]
    )

    # 3) Create a Gateway VPC Endpoint for S3
    s3_endpoint = aws.ec2.VpcEndpoint(
        "s3GatewayEndpoint",
        vpc_id=default_vpc.id,
        service_name=f"com.amazonaws.{aws.config.region}.s3",
        route_table_ids=[main_route_table.id],
        vpc_endpoint_type="Gateway",
    )

    return default_vpc, main_route_table, s3_endpoint
