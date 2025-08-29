"""Test CDK synthesis works correctly."""

import aws_cdk as cdk
from aws_cdk.assertions import Template

from stacks.backup_stack import BackupStack
from stacks.primary_app import PrimaryAppStack
from stacks.primary_data import PrimaryDataStack
from stacks.primary_network import PrimaryNetworkStack


def test_stacks_synthesize():
    """Test that all stacks synthesize without errors."""
    app = cdk.App()

    # Default config for testing
    config = {
        "primary_region": "us-east-1",
        "secondary_region": "us-west-2",
        "db_mode": "rds-postgres",
        "alarm_email": "test@example.com",
        "use_multi_region_kms": True,
        "rto_target_hours": 4,
        "rpo_target_hours": 4,
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

    env = cdk.Environment(account="123456789012", region="us-east-1")

    # Create stacks
    network_stack = PrimaryNetworkStack(app, "TestNetworkStack", env=env, config=config)

    data_stack = PrimaryDataStack(
        app, "TestDataStack", vpc=network_stack.vpc, env=env, config=config
    )

    app_stack = PrimaryAppStack(
        app,
        "TestAppStack",
        vpc=network_stack.vpc,
        database=data_stack.database,
        s3_bucket=data_stack.app_data_bucket,
        env=env,
        config=config,
    )

    backup_stack = BackupStack(
        app,
        "TestBackupStack",
        primary_vpc=network_stack.vpc,
        rds_instance=data_stack.database,
        s3_bucket=data_stack.app_data_bucket,
        kms_key=data_stack.kms_key,
        config=config,
        env=env,
    )

    # Test synthesis
    template_network = Template.from_stack(network_stack)
    template_data = Template.from_stack(data_stack)
    template_app = Template.from_stack(app_stack)
    template_backup = Template.from_stack(backup_stack)

    # Basic assertions - just ensure key resources exist
    template_network.has_resource_properties(
        "AWS::EC2::VPC", {"CidrBlock": "10.0.0.0/16"}
    )

    template_data.has_resource_properties(
        "AWS::RDS::DBInstance", {"Engine": "postgres"}
    )

    template_app.has_resource_properties("AWS::ECS::Cluster", {})

    template_backup.has_resource_properties("AWS::Backup::BackupPlan", {})
