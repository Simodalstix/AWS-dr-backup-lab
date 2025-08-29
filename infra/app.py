#!/usr/bin/env python3
"""
DR Lab - Backup and Restore Pattern
Simplified CDK application for backup and restore disaster recovery
"""

import aws_cdk as cdk
from aws_cdk import Environment

from stacks.backup_stack import BackupStack
from stacks.primary_app import PrimaryAppStack
from stacks.primary_data import PrimaryDataStack
from stacks.primary_network import PrimaryNetworkStack


def main():
    app = cdk.App()

    # Get configuration from context
    config = app.node.try_get_context("config") or {}

    # Default configuration for backup and restore
    default_config = {
        "primary_region": "ap-southeast-2",
        "secondary_region": "us-west-2",
        "db_mode": "rds-postgres",
        "alarm_email": "admin@example.com",
        "use_multi_region_kms": True,
        "rto_target_hours": 4,  # 4 hours RTO
        "rpo_target_hours": 4,  # 4 hours RPO
        "domain_name": "app.example.com",
        "vpc_cidr": "10.0.0.0/16",
        "ecs_cpu": 256,
        "ecs_memory": 512,
        "container_image": "nginx:latest",
        "container_port": 80,
        "db_instance_class": "db.t3.micro",
        "db_allocated_storage": 20,
        "db_backup_retention": 7,
    }

    # Merge configurations
    config = {**default_config, **config}

    # Account and regions
    account = app.account or "820242933814"
    primary_region = config["primary_region"]

    # Environment definition (only primary region needed)
    primary_env = Environment(account=account, region=primary_region)

    # Primary region stacks (production workload)
    primary_network = PrimaryNetworkStack(
        app,
        "PrimaryNetworkStack",
        env=primary_env,
        config=config,
        description="Primary region network infrastructure",
    )

    primary_data = PrimaryDataStack(
        app,
        "PrimaryDataStack",
        vpc=primary_network.vpc,
        env=primary_env,
        config=config,
        description="Primary region data infrastructure with backup configuration",
    )

    # Primary application stack - demonstrates the workload being backed up
    primary_app = PrimaryAppStack(
        app,
        "PrimaryAppStack",
        vpc=primary_network.vpc,
        database=primary_data.database,
        s3_bucket=primary_data.app_data_bucket,
        env=primary_env,
        config=config,
        description="Primary region application infrastructure (workload to backup)",
    )

    # Backup stack - this is the core of our backup and restore pattern
    backup_stack = BackupStack(
        app,
        "BackupStack",
        primary_vpc=primary_network.vpc,
        rds_instance=primary_data.database,
        s3_bucket=primary_data.app_data_bucket,
        kms_key=primary_data.kms_key,
        config=config,
        env=primary_env,
        description="Backup and restore infrastructure for disaster recovery",
    )

    # Dependencies are automatically resolved by CDK based on resource references
    # No need to explicitly declare them

    # Add tags to all stacks
    tags = {
        "Project": "DR-Lab",
        "Pattern": "BackupAndRestore",
        "Environment": "Production",
        "Owner": "Platform-Team",
        "CostOptimized": "True",
    }

    for stack in [primary_network, primary_data, primary_app, backup_stack]:
        for key, value in tags.items():
            cdk.Tags.of(stack).add(key, value)

    app.synth()


if __name__ == "__main__":
    main()
