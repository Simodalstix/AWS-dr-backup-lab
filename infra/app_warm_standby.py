#!/usr/bin/env python3
"""
Tier-2 Backup & DR Lab (Multi-Region Warm Standby)
Main CDK application entry point
"""

import aws_cdk as cdk
from aws_cdk import Environment

from stacks.primary_network import PrimaryNetworkStack
from stacks.primary_app import PrimaryAppStack
from stacks.primary_data import PrimaryDataStack
from stacks.secondary_network import SecondaryNetworkStack
from stacks.secondary_app import SecondaryAppStack
from stacks.secondary_data import SecondaryDataStack
from stacks.routing_dr_orchestration import RoutingAndDROrchestrationStack
from stacks.observability import ObservabilityStack


def main():
    app = cdk.App()

    # Get configuration from context
    config = app.node.try_get_context("config") or {}

    # Default configuration
    default_config = {
        "primary_region": "ap-southeast-2",
        "secondary_region": "us-west-2",
        "db_mode": "rds-postgres",
        "warm_standby_tasks": 1,
        "alarm_email": "admin@example.com",
        "use_multi_region_kms": True,
        "s3_replicate_deletes": False,
        "rto_target_minutes": 30,
        "rpo_target_seconds": 300,
        "canary_enabled": False,
        "domain_name": "app.example.com",
        "hosted_zone_id": None,
        "vpc_cidr": "10.0.0.0/16",
    }

    # Merge configurations
    config = {**default_config, **config}

    # Account and regions
    account = app.account or "123456789012"  # Will be replaced with actual account
    primary_region = config["primary_region"]
    secondary_region = config["secondary_region"]

    # Environment definitions
    primary_env = Environment(account=account, region=primary_region)
    secondary_env = Environment(account=account, region=secondary_region)

    # Primary region stacks
    primary_network = PrimaryNetworkStack(
        app,
        "PrimaryNetworkStack",
        env=primary_env,
        config=config,
        description="Primary region network infrastructure for DR lab",
    )

    primary_data = PrimaryDataStack(
        app,
        "PrimaryDataStack",
        vpc=primary_network.vpc,
        env=primary_env,
        config=config,
        description="Primary region data infrastructure for DR lab",
    )

    primary_app = PrimaryAppStack(
        app,
        "PrimaryAppStack",
        vpc=primary_network.vpc,
        database=primary_data.database,
        s3_bucket=primary_data.app_data_bucket,
        env=primary_env,
        config=config,
        description="Primary region application infrastructure for DR lab",
    )

    # Secondary region stacks
    secondary_network = SecondaryNetworkStack(
        app,
        "SecondaryNetworkStack",
        env=secondary_env,
        config=config,
        description="Secondary region network infrastructure for DR lab",
    )

    secondary_data = SecondaryDataStack(
        app,
        "SecondaryDataStack",
        vpc=secondary_network.vpc,
        primary_database=primary_data.database,
        primary_s3_bucket=primary_data.app_data_bucket,
        primary_kms_key=primary_data.kms_key,
        env=secondary_env,
        config=config,
        description="Secondary region data infrastructure for DR lab",
    )

    secondary_app = SecondaryAppStack(
        app,
        "SecondaryAppStack",
        vpc=secondary_network.vpc,
        database=secondary_data.database_replica,
        s3_bucket=secondary_data.app_data_bucket,
        env=secondary_env,
        config=config,
        description="Secondary region application infrastructure for DR lab",
    )

    # Global stacks (deployed to primary region but manage global resources)
    routing_dr = RoutingAndDROrchestrationStack(
        app,
        "RoutingAndDROrchestrationStack",
        primary_alb=primary_app.load_balancer,
        secondary_alb=secondary_app.load_balancer,
        primary_database=primary_data.database,
        secondary_database=secondary_data.database_replica,
        primary_ecs_service=primary_app.ecs_service,
        secondary_ecs_service=secondary_app.ecs_service,
        env=primary_env,
        config=config,
        description="Global routing and DR orchestration for DR lab",
    )

    observability = ObservabilityStack(
        app,
        "ObservabilityStack",
        primary_alb=primary_app.load_balancer,
        secondary_alb=secondary_app.load_balancer,
        primary_database=primary_data.database,
        secondary_database=secondary_data.database_replica,
        primary_ecs_service=primary_app.ecs_service,
        secondary_ecs_service=secondary_app.ecs_service,
        s3_buckets=[primary_data.app_data_bucket, secondary_data.app_data_bucket],
        env=primary_env,
        config=config,
        description="Observability and monitoring for DR lab",
    )

    # Stack dependencies
    primary_data.add_dependency(primary_network)
    primary_app.add_dependency(primary_data)

    secondary_data.add_dependency(secondary_network)
    secondary_data.add_dependency(primary_data)  # Needs primary DB for replica
    secondary_app.add_dependency(secondary_data)

    routing_dr.add_dependency(primary_app)
    routing_dr.add_dependency(secondary_app)

    observability.add_dependency(primary_app)
    observability.add_dependency(secondary_app)
    observability.add_dependency(routing_dr)

    # Add tags to all stacks
    tags = {
        "Project": "DR-Lab",
        "Environment": "Production",
        "Owner": "Platform-Team",
        "CostCenter": "Infrastructure",
    }

    for stack in [
        primary_network,
        primary_data,
        primary_app,
        secondary_network,
        secondary_data,
        secondary_app,
        routing_dr,
        observability,
    ]:
        for key, value in tags.items():
            cdk.Tags.of(stack).add(key, value)

    app.synth()


if __name__ == "__main__":
    main()
