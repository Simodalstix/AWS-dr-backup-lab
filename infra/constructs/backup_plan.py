"""
BackupPlan Construct
Simple AWS Backup integration with cross-region copying.
"""

from typing import Optional

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_backup as backup
from aws_cdk import aws_events as events
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_sns as sns

from constructs import Construct


class BackupPlan(Construct):
    """
    A focused construct that creates AWS Backup plans with cross-region copying.

    This construct provides:
    - AWS Backup vault in primary region
    - Backup plans for RDS and S3 resources
    - Cross-region backup copying
    - Basic backup monitoring
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        primary_region: str,
        secondary_region: str,
        kms_key: kms.IKey,
        backup_retention_days: int = 30,
        notification_topic: Optional[sns.ITopic] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._primary_region = primary_region
        self._secondary_region = secondary_region
        self._kms_key = kms_key
        self._backup_retention_days = backup_retention_days
        self._notification_topic = notification_topic

        # Create backup vault
        self._create_backup_vault()

        # Create backup service role
        self._create_backup_role()

        # Create backup plans
        self._create_backup_plans()

        # Create outputs
        self._create_outputs()

    def _create_backup_vault(self) -> None:
        """Create backup vault in primary region."""

        self._primary_vault = backup.BackupVault(
            self,
            "PrimaryBackupVault",
            backup_vault_name=f"dr-lab-backup-vault-{self._primary_region}",
            encryption_key=self._kms_key,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def _create_backup_role(self) -> None:
        """Create IAM role for AWS Backup service."""

        self._backup_role = iam.Role(
            self,
            "BackupRole",
            assumed_by=iam.ServicePrincipal("backup.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSBackupServiceRolePolicyForBackup"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSBackupServiceRolePolicyForRestores"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSBackupServiceRolePolicyForS3Backup"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSBackupServiceRolePolicyForS3Restore"
                ),
            ],
        )

    def _create_backup_plans(self) -> None:
        """Create backup plans for RDS and S3."""

        # RDS Backup Plan - Hourly backups
        self._rds_backup_plan = backup.BackupPlan(
            self,
            "RDSBackupPlan",
            backup_plan_name="dr-lab-rds-backup-plan",
            backup_plan_rules=[
                backup.BackupPlanRule(
                    backup_vault=self._primary_vault,
                    rule_name="HourlyRDSBackup",
                    schedule_expression=events.Schedule.expression("cron(0 * * * ? *)"),
                    start_window=Duration.hours(1),
                    completion_window=Duration.hours(2),
                    delete_after=Duration.days(self._backup_retention_days),
                    copy_actions=[
                        backup.BackupPlanCopyActionProps(
                            destination_backup_vault=backup.BackupVault.from_backup_vault_name(
                                self,
                                "SecondaryVaultRef1",
                                f"dr-lab-backup-vault-{self._secondary_region}",
                            ),
                            delete_after=Duration.days(self._backup_retention_days),
                        )
                    ],
                    recovery_point_tags={
                        "BackupType": "RDS",
                        "Environment": "Production",
                        "Project": "DR-Lab",
                    },
                )
            ],
        )

        # S3 Backup Plan - Every 4 hours
        self._s3_backup_plan = backup.BackupPlan(
            self,
            "S3BackupPlan",
            backup_plan_name="dr-lab-s3-backup-plan",
            backup_plan_rules=[
                backup.BackupPlanRule(
                    backup_vault=self._primary_vault,
                    rule_name="QuadHourlyS3Backup",
                    schedule_expression=events.Schedule.expression(
                        "cron(0 */4 * * ? *)"
                    ),
                    start_window=Duration.hours(1),
                    completion_window=Duration.hours(3),
                    delete_after=Duration.days(self._backup_retention_days),
                    copy_actions=[
                        backup.BackupPlanCopyActionProps(
                            destination_backup_vault=backup.BackupVault.from_backup_vault_name(
                                self,
                                "SecondaryVaultRef2",
                                f"dr-lab-backup-vault-{self._secondary_region}",
                            ),
                            delete_after=Duration.days(self._backup_retention_days),
                        )
                    ],
                    recovery_point_tags={
                        "BackupType": "S3",
                        "Environment": "Production",
                        "Project": "DR-Lab",
                    },
                )
            ],
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "PrimaryBackupVaultName",
            value=self._primary_vault.backup_vault_name,
            description="Name of the primary backup vault",
            export_name=f"{Stack.of(self).stack_name}-PrimaryBackupVaultName",
        )

        CfnOutput(
            self,
            "PrimaryBackupVaultArn",
            value=self._primary_vault.backup_vault_arn,
            description="ARN of the primary backup vault",
            export_name=f"{Stack.of(self).stack_name}-PrimaryBackupVaultArn",
        )

        CfnOutput(
            self,
            "RDSBackupPlanId",
            value=self._rds_backup_plan.backup_plan_id,
            description="ID of the RDS backup plan",
            export_name=f"{Stack.of(self).stack_name}-RDSBackupPlanId",
        )

        CfnOutput(
            self,
            "S3BackupPlanId",
            value=self._s3_backup_plan.backup_plan_id,
            description="ID of the S3 backup plan",
            export_name=f"{Stack.of(self).stack_name}-S3BackupPlanId",
        )

    @property
    def primary_backup_vault(self) -> backup.BackupVault:
        """Get the primary backup vault."""
        return self._primary_vault

    @property
    def rds_backup_plan(self) -> backup.BackupPlan:
        """Get the RDS backup plan."""
        return self._rds_backup_plan

    @property
    def s3_backup_plan(self) -> backup.BackupPlan:
        """Get the S3 backup plan."""
        return self._s3_backup_plan

    @property
    def backup_role(self) -> iam.Role:
        """Get the backup service role."""
        return self._backup_role

    def add_resource_selection(
        self, resource_arn: str, backup_plan: backup.BackupPlan
    ) -> backup.BackupSelection:
        """Add a resource to backup plan."""
        return backup.BackupSelection(
            self,
            f"BackupSelection{hash(resource_arn) % 10000}",
            backup_plan=backup_plan,
            backup_selection_name=f"selection-{hash(resource_arn) % 10000}",
            role=self._backup_role,
            resources=[
                backup.BackupResource.from_arn(resource_arn),
            ],
        )
