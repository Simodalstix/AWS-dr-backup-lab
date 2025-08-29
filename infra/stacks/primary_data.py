"""
Primary Data Stack
Creates the data infrastructure in the primary region.
"""

from typing import Dict

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    Tags,
)
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3

from constructs import Construct
from constructs.kms_multi_region_key import KMSMultiRegionKey
from constructs.rds_with_replica import RDSWithReplica
from constructs.s3_replication_pair import S3ReplicationPair


class PrimaryDataStack(Stack):
    """
    Stack that creates the data infrastructure for the primary region.

    This stack creates:
    - KMS keys for encryption
    - RDS primary instance (PostgreSQL)
    - S3 buckets for application data and logs
    - Security configurations
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        config: Dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._vpc = vpc
        self._config = config

        # Create KMS keys
        self._create_kms_keys()

        # Create RDS database
        self._create_database()

        # Create S3 buckets
        self._create_s3_buckets()

        # Create outputs
        self._create_outputs()

        # Add tags
        self._add_tags()

    def _create_kms_keys(self) -> None:
        """Create KMS keys for encryption."""

        # Main encryption key for data
        self._kms_key = KMSMultiRegionKey(
            self,
            "DataEncryptionKey",
            alias="dr-lab-data-key",
            description="Multi-region KMS key for DR lab data encryption",
            enable_key_rotation=True,
            replica_regions=[self._config.get("secondary_region", "us-west-2")],
        )

        # Separate key for logs
        self._logs_kms_key = KMSMultiRegionKey(
            self,
            "LogsEncryptionKey",
            alias="dr-lab-logs-key",
            description="Multi-region KMS key for DR lab logs encryption",
            enable_key_rotation=True,
            replica_regions=[self._config.get("secondary_region", "us-west-2")],
        )

    def _create_database(self) -> None:
        """Create the RDS database."""

        # Get database configuration
        db_config = {
            "instance_class": ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize(
                    self._config.get("db_instance_class", "db.t3.micro")
                    .split(".")[-1]
                    .upper()
                ),
            ),
            "allocated_storage": self._config.get("db_allocated_storage", 20),
            "backup_retention": Duration.days(
                self._config.get("db_backup_retention", 7)
            ),
            "database_name": "drlab",
            "username": "admin",
            "kms_key": self._kms_key.key,
            "replica_region": self._config.get("secondary_region"),
            "enable_performance_insights": True,
            "monitoring_interval": Duration.seconds(60),
            "enable_logging": True,
            "log_types": ["postgresql"],
        }

        # Create RDS instance with replica configuration
        self._database = RDSWithReplica(self, "Database", vpc=self._vpc, **db_config)

        # Database security is handled within the RDSWithReplica construct
        # No additional security group rules needed here

    def _create_s3_buckets(self) -> None:
        """Create S3 buckets for application data and logs."""

        # Application data bucket with replication
        self._app_data_bucket_construct = S3ReplicationPair(
            self,
            "AppDataBucket",
            source_region=self._config.get("primary_region", "ap-southeast-2"),
            destination_region=self._config.get("secondary_region", "us-west-2"),
            bucket_name_prefix="dr-lab-app-data",
            versioned=True,
            replicate_deletes=self._config.get("s3_replicate_deletes", False),
            kms_key=self._kms_key.key,
            destination_kms_key=self._kms_key.key,  # Multi-region key works in both regions
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToGlacier",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(
                                self._config.get("s3_lifecycle_glacier_days", 90)
                            ),
                        )
                    ],
                ),
                s3.LifecycleRule(
                    id="DeleteIncompleteMultipartUploads",
                    enabled=True,
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                ),
            ],
            enable_access_logging=True,
        )

        # Logs bucket (no replication needed for logs)
        self._logs_bucket = s3.Bucket(
            self,
            "LogsBucket",
            bucket_name=f"dr-lab-logs-{self._config.get('primary_region', 'ap-southeast-2')}",
            versioned=False,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self._logs_kms_key.key,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldLogs",
                    enabled=True,
                    expiration=Duration.days(
                        self._config.get("cloudwatch_log_retention_days", 14) * 2
                    ),
                ),
            ],
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        # CloudWatch Logs destination bucket
        self._cloudwatch_logs_bucket = s3.Bucket(
            self,
            "CloudWatchLogsBucket",
            bucket_name=f"dr-lab-cloudwatch-logs-{self._config.get('primary_region', 'ap-southeast-2')}",
            versioned=False,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self._logs_kms_key.key,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldCloudWatchLogs",
                    enabled=True,
                    expiration=Duration.days(90),
                )
            ],
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        # KMS Key outputs
        CfnOutput(
            self,
            "KMSKeyId",
            value=self._kms_key.key_id,
            description="ID of the main KMS key",
            export_name=f"{self.stack_name}-KMSKeyId",
        )

        CfnOutput(
            self,
            "KMSKeyArn",
            value=self._kms_key.key_arn,
            description="ARN of the main KMS key",
            export_name=f"{self.stack_name}-KMSKeyArn",
        )

        CfnOutput(
            self,
            "LogsKMSKeyId",
            value=self._logs_kms_key.key_id,
            description="ID of the logs KMS key",
            export_name=f"{self.stack_name}-LogsKMSKeyId",
        )

        # Database outputs
        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=self._database.primary_instance.instance_endpoint.hostname,
            description="Primary database endpoint",
            export_name=f"{self.stack_name}-DatabaseEndpoint",
        )

        CfnOutput(
            self,
            "DatabasePort",
            value=str(self._database.primary_instance.instance_endpoint.port),
            description="Primary database port",
            export_name=f"{self.stack_name}-DatabasePort",
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=self._database.secret.secret_arn,
            description="ARN of the database credentials secret",
            export_name=f"{self.stack_name}-DatabaseSecretArn",
        )

        # S3 bucket outputs
        CfnOutput(
            self,
            "AppDataBucketName",
            value=self._app_data_bucket_construct.source_bucket.bucket_name,
            description="Name of the application data bucket",
            export_name=f"{self.stack_name}-AppDataBucketName",
        )

        CfnOutput(
            self,
            "AppDataBucketArn",
            value=self._app_data_bucket_construct.source_bucket.bucket_arn,
            description="ARN of the application data bucket",
            export_name=f"{self.stack_name}-AppDataBucketArn",
        )

        CfnOutput(
            self,
            "LogsBucketName",
            value=self._logs_bucket.bucket_name,
            description="Name of the logs bucket",
            export_name=f"{self.stack_name}-LogsBucketName",
        )

        CfnOutput(
            self,
            "CloudWatchLogsBucketName",
            value=self._cloudwatch_logs_bucket.bucket_name,
            description="Name of the CloudWatch logs bucket",
            export_name=f"{self.stack_name}-CloudWatchLogsBucketName",
        )

    def _add_tags(self) -> None:
        """Add tags to all resources in this stack."""

        Tags.of(self).add("Component", "Data")
        Tags.of(self).add("Region", "Primary")
        Tags.of(self).add("Environment", "Production")

    @property
    def kms_key(self) -> KMSMultiRegionKey:
        """Get the main KMS key."""
        return self._kms_key

    @property
    def logs_kms_key(self) -> KMSMultiRegionKey:
        """Get the logs KMS key."""
        return self._logs_kms_key

    @property
    def database(self) -> RDSWithReplica:
        """Get the database construct."""
        return self._database

    @property
    def app_data_bucket(self) -> s3.Bucket:
        """Get the application data bucket."""
        return self._app_data_bucket_construct.source_bucket

    @property
    def logs_bucket(self) -> s3.Bucket:
        """Get the logs bucket."""
        return self._logs_bucket

    @property
    def cloudwatch_logs_bucket(self) -> s3.Bucket:
        """Get the CloudWatch logs bucket."""
        return self._cloudwatch_logs_bucket

    @property
    def app_data_bucket_construct(self) -> S3ReplicationPair:
        """Get the application data bucket construct."""
        return self._app_data_bucket_construct
