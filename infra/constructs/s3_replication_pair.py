"""
S3 Replication Pair Construct
Creates S3 buckets with cross-region replication configuration.
"""

from typing import Dict, List, Optional

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3

from constructs import Construct


class S3ReplicationPair(Construct):
    """
    A construct that creates S3 buckets with cross-region replication.

    This construct creates a source bucket in the current region and configures
    cross-region replication to a destination bucket in another region.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        source_region: str,
        destination_region: str,
        bucket_name_prefix: str,
        versioned: bool = True,
        replicate_deletes: bool = False,
        kms_key: Optional[kms.IKey] = None,
        destination_kms_key: Optional[kms.IKey] = None,
        lifecycle_rules: Optional[List[s3.LifecycleRule]] = None,
        enable_access_logging: bool = False,
        access_log_bucket: Optional[s3.IBucket] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._source_region = source_region
        self._destination_region = destination_region
        self._bucket_name_prefix = bucket_name_prefix
        self._versioned = versioned
        self._replicate_deletes = replicate_deletes
        self._kms_key = kms_key
        self._destination_kms_key = destination_kms_key or kms_key
        self._lifecycle_rules = lifecycle_rules or []
        self._enable_access_logging = enable_access_logging
        self._access_log_bucket = access_log_bucket

        # Create replication role
        self._create_replication_role()

        # Create source bucket
        self._create_source_bucket()

        # Create destination bucket (conceptually - actual creation happens in destination region)
        self._create_destination_bucket_config()

        # Configure replication
        self._configure_replication()

        # Create access logging bucket if needed
        if self._enable_access_logging and not self._access_log_bucket:
            self._create_access_log_bucket()

        # Create outputs
        self._create_outputs()

    def _create_replication_role(self) -> None:
        """Create IAM role for S3 replication."""

        self._replication_role = iam.Role(
            self,
            "ReplicationRole",
            assumed_by=iam.ServicePrincipal("s3.amazonaws.com"),
            description="Role for S3 cross-region replication",
        )

        # Add basic replication permissions
        self._replication_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObjectVersionForReplication",
                    "s3:GetObjectVersionAcl",
                    "s3:GetObjectVersionTagging",
                ],
                resources=[
                    f"arn:aws:s3:::{self._bucket_name_prefix}-{self._source_region}/*"
                ],
            )
        )

        self._replication_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::{self._bucket_name_prefix}-{self._source_region}"
                ],
            )
        )

        self._replication_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                ],
                resources=[
                    f"arn:aws:s3:::{self._bucket_name_prefix}-{self._destination_region}/*"
                ],
            )
        )

        # Add KMS permissions if encryption is enabled
        if self._kms_key:
            self._replication_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "kms:Decrypt",
                        "kms:GenerateDataKey",
                    ],
                    resources=[self._kms_key.key_arn],
                )
            )

        if self._destination_kms_key and self._destination_kms_key != self._kms_key:
            self._replication_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "kms:Encrypt",
                        "kms:GenerateDataKey",
                    ],
                    resources=[self._destination_kms_key.key_arn],
                )
            )

    def _create_source_bucket(self) -> None:
        """Create the source S3 bucket."""

        # Configure server access logging
        server_access_logs_config = None
        if self._enable_access_logging:
            if self._access_log_bucket:
                server_access_logs_config = s3.BucketLogging(
                    destination_bucket=self._access_log_bucket,
                    object_key_prefix=f"{self._bucket_name_prefix}-{self._source_region}/access-logs/",
                )

        self._source_bucket = s3.Bucket(
            self,
            "SourceBucket",
            bucket_name=f"{self._bucket_name_prefix}-{self._source_region}",
            versioned=self._versioned,
            encryption=(
                s3.BucketEncryption.KMS
                if self._kms_key
                else s3.BucketEncryption.S3_MANAGED
            ),
            encryption_key=self._kms_key,
            lifecycle_rules=self._lifecycle_rules,
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            server_access_logs_bucket=(
                self._access_log_bucket if self._enable_access_logging else None
            ),
            server_access_logs_prefix=(
                f"{self._bucket_name_prefix}-{self._source_region}/access-logs/"
                if self._enable_access_logging
                else None
            ),
            removal_policy=RemovalPolicy.RETAIN,  # Protect data
        )

    def _create_destination_bucket_config(self) -> None:
        """Create configuration for destination bucket (to be created in destination region)."""

        # This creates the configuration that will be used by the destination region stack
        # The actual bucket creation happens in the destination region
        self._destination_bucket_config = {
            "bucket_name": f"{self._bucket_name_prefix}-{self._destination_region}",
            "versioned": self._versioned,
            "encryption": (
                s3.BucketEncryption.KMS
                if self._destination_kms_key
                else s3.BucketEncryption.S3_MANAGED
            ),
            "encryption_key": self._destination_kms_key,
            "lifecycle_rules": self._lifecycle_rules,
            "public_read_access": False,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "enforce_ssl": True,
            "removal_policy": RemovalPolicy.RETAIN,
        }

    def _configure_replication(self) -> None:
        """Configure cross-region replication on the source bucket."""

        # Add replication configuration to source bucket using CFN properties
        cfn_bucket = self._source_bucket.node.default_child

        # Build the replication rule
        replication_rule = s3.CfnBucket.ReplicationRuleProperty(
            id="ReplicateToSecondaryRegion",
            status="Enabled",
            prefix="",  # Replicate all objects
            destination=s3.CfnBucket.ReplicationDestinationProperty(
                bucket=f"arn:aws:s3:::{self._bucket_name_prefix}-{self._destination_region}",
                storage_class="STANDARD_IA",
                encryption_configuration=(
                    s3.CfnBucket.EncryptionConfigurationProperty(
                        replica_kms_key_id=self._destination_kms_key.key_arn
                    )
                    if self._destination_kms_key
                    else None
                ),
            ),
            delete_marker_replication=s3.CfnBucket.DeleteMarkerReplicationProperty(
                status="Enabled" if self._replicate_deletes else "Disabled"
            ),
        )

        # Set the replication configuration
        cfn_bucket.replication_configuration = (
            s3.CfnBucket.ReplicationConfigurationProperty(
                role=self._replication_role.role_arn,
                rules=[replication_rule],
            )
        )

    def _create_access_log_bucket(self) -> None:
        """Create access log bucket if needed."""

        self._access_log_bucket = s3.Bucket(
            self,
            "AccessLogBucket",
            bucket_name=f"{self._bucket_name_prefix}-access-logs-{self._source_region}",
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldAccessLogs",
                    enabled=True,
                    expiration=Duration.days(90),
                )
            ],
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,  # Access logs can be destroyed
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "SourceBucketName",
            value=self._source_bucket.bucket_name,
            description="Name of the source S3 bucket",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-SourceBucketName",
        )

        CfnOutput(
            self,
            "SourceBucketArn",
            value=self._source_bucket.bucket_arn,
            description="ARN of the source S3 bucket",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-SourceBucketArn",
        )

        CfnOutput(
            self,
            "DestinationBucketName",
            value=self._destination_bucket_config["bucket_name"],
            description="Name of the destination S3 bucket",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-DestinationBucketName",
        )

        CfnOutput(
            self,
            "ReplicationRoleArn",
            value=self._replication_role.role_arn,
            description="ARN of the S3 replication role",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-ReplicationRoleArn",
        )

        if hasattr(self, "_access_log_bucket") and self._access_log_bucket:
            CfnOutput(
                self,
                "AccessLogBucketName",
                value=self._access_log_bucket.bucket_name,
                description="Name of the access log bucket",
                export_name=f"{Stack.of(self).stack_name}-{self.node.id}-AccessLogBucketName",
            )

    @property
    def source_bucket(self) -> s3.Bucket:
        """Get the source S3 bucket."""
        return self._source_bucket

    @property
    def destination_bucket_config(self) -> Dict:
        """Get the destination bucket configuration."""
        return self._destination_bucket_config

    @property
    def replication_role(self) -> iam.Role:
        """Get the replication IAM role."""
        return self._replication_role

    @property
    def access_log_bucket(self) -> Optional[s3.Bucket]:
        """Get the access log bucket if created."""
        return getattr(self, "_access_log_bucket", None)

    def grant_read(self, identity: iam.IGrantable) -> iam.Grant:
        """Grant read permissions to the source bucket."""
        return self._source_bucket.grant_read(identity)

    def grant_write(self, identity: iam.IGrantable) -> iam.Grant:
        """Grant write permissions to the source bucket."""
        return self._source_bucket.grant_write(identity)

    def grant_read_write(self, identity: iam.IGrantable) -> iam.Grant:
        """Grant read/write permissions to the source bucket."""
        return self._source_bucket.grant_read_write(identity)

    def add_lifecycle_rule(self, rule: s3.LifecycleRule) -> None:
        """Add a lifecycle rule to the source bucket."""
        # Note: This would require recreating the bucket in CDK
        # Better to pass all lifecycle rules during construction
        pass

    def add_cors_rule(self, rule: s3.CorsRule) -> None:
        """Add a CORS rule to the source bucket."""
        self._source_bucket.add_cors_rule(**rule.__dict__)

    def add_event_notification(
        self,
        event: s3.EventType,
        dest: s3.IBucketNotificationDestination,
        *filters: s3.NotificationKeyFilter,
    ) -> None:
        """Add an event notification to the source bucket."""
        self._source_bucket.add_event_notification(event, dest, *filters)
