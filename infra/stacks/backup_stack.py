"""
Backup Stack
Simple backup and restore capabilities for DR lab.
"""

from typing import Dict
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    CfnOutput,
    Tags,
)
from constructs import Construct

from constructs.backup_plan import BackupPlan
from constructs.template_storage import TemplateStorage
from constructs.deployment_automation import DeploymentAutomation
from constructs.recovery_parameters import RecoveryParameters
from constructs.kms_multi_region_key import KMSMultiRegionKey
from constructs.secrets_manager import SecretsManager


class BackupStack(Stack):
    """
    Stack that implements simple backup and restore capabilities.

    This stack creates:
    - AWS Backup plans with cross-region copying
    - Recovery templates for emergency deployment
    - Deployment automation functions
    - Recovery configuration parameters
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        primary_vpc: ec2.Vpc,
        rds_instance: rds.DatabaseInstance,
        s3_bucket: s3.Bucket,
        kms_key: KMSMultiRegionKey,
        config: Dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._primary_vpc = primary_vpc
        self._rds_instance = rds_instance
        self._s3_bucket = s3_bucket
        self._kms_key = kms_key
        self._config = config

        # Create notification topic
        self._create_notification_topic()

        # Create backup plan
        self._create_backup_plan()

        # Create recovery templates
        self._create_recovery_templates()

        # Create secrets manager
        self._create_secrets_manager()

        # Create deployment automation
        self._create_deployment_automation()

        # Create recovery parameters
        self._create_recovery_parameters()

        # Create backup selections
        self._create_backup_selections()

        # Create outputs
        self._create_outputs()

        # Add tags
        self._add_tags()

    def _create_notification_topic(self) -> None:
        """Create SNS topic for backup notifications."""

        self._notification_topic = sns.Topic(
            self,
            "BackupNotificationTopic",
            display_name="DR Lab Backup Notifications",
            topic_name="dr-lab-backup-notifications",
        )

        # Add email subscription if configured
        alarm_email = self._config.get("alarm_email")
        if alarm_email:
            self._notification_topic.add_subscription(
                subs.EmailSubscription(alarm_email)
            )

    def _create_backup_plan(self) -> None:
        """Create AWS Backup plan with cross-region copying."""

        self._backup_plan = BackupPlan(
            self,
            "BackupPlan",
            primary_region=self._config.get("primary_region", "ap-southeast-2"),
            secondary_region=self._config.get("secondary_region", "us-west-2"),
            kms_key=self._kms_key.key,
            backup_retention_days=30,
            notification_topic=self._notification_topic,
        )

    def _create_recovery_templates(self) -> None:
        """Create recovery templates for emergency deployment."""

        self._template_storage = TemplateStorage(
            self,
            "TemplateStorage",
            region=self._config.get("secondary_region", "us-west-2"),
            template_files=[
                "network-template.json",
                "application-template.json",
            ],
        )

    def _create_secrets_manager(self) -> None:
        """Create secrets manager for application configuration."""

        self._secrets_manager = SecretsManager(
            self,
            "SecretsManager",
            kms_key=self._kms_key.key,
            replica_regions=[self._config.get("secondary_region", "us-west-2")],
        )

    def _create_deployment_automation(self) -> None:
        """Create deployment automation functions."""

        self._deployment_automation = DeploymentAutomation(
            self,
            "DeploymentAutomation",
            template_bucket=self._template_storage.template_bucket,
            primary_region=self._config.get("primary_region", "ap-southeast-2"),
            secondary_region=self._config.get("secondary_region", "us-west-2"),
        )

    def _create_recovery_parameters(self) -> None:
        """Create recovery configuration parameters."""

        self._recovery_parameters = RecoveryParameters(
            self,
            "RecoveryParameters",
            primary_region=self._config.get("primary_region", "ap-southeast-2"),
            secondary_region=self._config.get("secondary_region", "us-west-2"),
            vpc_cidr="10.1.0.0/16",  # Different CIDR for recovery environment
            availability_zones=2,
            ecs_cpu=self._config.get("ecs_cpu", 256),
            ecs_memory=self._config.get("ecs_memory", 512),
            container_image=self._config.get("container_image", "nginx:latest"),
            container_port=self._config.get("container_port", 80),
            template_bucket_name=self._template_storage.bucket_name,
        )

    def _create_backup_selections(self) -> None:
        """Create backup selections for RDS and S3."""

        # Add RDS instance to backup
        self._rds_backup_selection = self._backup_plan.add_resource_selection(
            resource_arn=self._rds_instance.primary_instance.instance_arn,
            backup_plan=self._backup_plan.rds_backup_plan,
        )

        # Add S3 bucket to backup
        self._s3_backup_selection = self._backup_plan.add_resource_selection(
            resource_arn=self._s3_bucket.bucket_arn,
            backup_plan=self._backup_plan.s3_backup_plan,
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        # Backup outputs
        CfnOutput(
            self,
            "BackupVaultName",
            value=self._backup_plan.primary_backup_vault.backup_vault_name,
            description="Name of the primary backup vault",
            export_name=f"{self.stack_name}-BackupVaultName",
        )

        # Recovery outputs
        CfnOutput(
            self,
            "RecoveryTemplateBucket",
            value=self._template_storage.bucket_name,
            description="Name of the recovery templates bucket",
            export_name=f"{self.stack_name}-RecoveryTemplateBucket",
        )

        CfnOutput(
            self,
            "DeploymentFunctionArn",
            value=self._deployment_automation.stack_deployment_function.function_arn,
            description="ARN of the deployment automation function",
            export_name=f"{self.stack_name}-DeploymentFunctionArn",
        )

        # Recovery instructions
        CfnOutput(
            self,
            "RecoveryInstructions",
            value=f"1. Restore from backup vault: {self._backup_plan.primary_backup_vault.backup_vault_name} 2. Deploy templates from: {self._template_storage.bucket_name} 3. Use deployment function: {self._deployment_automation.stack_deployment_function.function_name}",
            description="Simple recovery instructions",
            export_name=f"{self.stack_name}-RecoveryInstructions",
        )

        # Cost summary
        CfnOutput(
            self,
            "CostSummary",
            value="Backup & Restore pattern: ~$50/month (87% reduction from $377 warm standby). RTO: 3-4 hours, RPO: 1-4 hours",
            description="Cost and performance summary",
            export_name=f"{self.stack_name}-CostSummary",
        )

    def _add_tags(self) -> None:
        """Add tags to all resources in this stack."""

        Tags.of(self).add("Component", "Backup")
        Tags.of(self).add("Pattern", "BackupAndRestore")
        Tags.of(self).add("CostOptimized", "True")

    @property
    def backup_plan(self) -> BackupPlan:
        """Get the backup plan construct."""
        return self._backup_plan

    @property
    def template_storage(self) -> TemplateStorage:
        """Get the template storage construct."""
        return self._template_storage

    @property
    def secrets_manager(self) -> SecretsManager:
        """Get the secrets manager construct."""
        return self._secrets_manager

    @property
    def deployment_automation(self) -> DeploymentAutomation:
        """Get the deployment automation construct."""
        return self._deployment_automation
