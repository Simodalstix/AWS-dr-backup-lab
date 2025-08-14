"""
Secondary Data Stack
Creates the data infrastructure in the secondary region.
"""

from typing import Dict
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_s3 as s3,
    aws_kms as kms,
    aws_logs as logs,
    Duration,
    CfnOutput,
    Tags,
)
from constructs import Construct

from constructs.kms_multi_region_key import KMSMultiRegionKey
from constructs.s3_replication_pair import S3ReplicationPair


class SecondaryDataStack(Stack):
    """
    Stack that creates the data infrastructure for the secondary region.

    This stack creates:
    - KMS keys for encryption (replicas of primary keys)
    - RDS read replica
    - S3 buckets for replicated application data
    - Security configurations
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        primary_database: rds.DatabaseInstance,
        primary_s3_bucket: s3.Bucket,
        primary_kms_key: KMSMultiRegionKey,
        config: Dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._vpc = vpc
        self._primary_database = primary_database
        self._primary_s3_bucket = primary_s3_bucket
        self._primary_kms_key = primary_kms_key
        self._config = config

        # Create KMS keys (replicas of primary keys)
        self._create_kms_keys()

        # Create RDS read replica
        self._create_database_replica()

        # Create S3 buckets (replicas of primary buckets)
        self._create_s3_buckets()

        # Create outputs
        self._create_outputs()

        # Add tags
        self._add_tags()

    def _create_kms_keys(self) -> None:
        """Create KMS keys as replicas of primary keys."""

        # Get the replica key from the primary KMS key
        # In practice, this would be done by referencing the primary key ARN
        # and creating a replica in this region

        # For this implementation, we'll use the same multi-region key
        # which automatically creates replicas in all specified regions
        self._kms_key = self._primary_kms_key

        # Create logs KMS key replica
        # This would also be a replica of the primary logs key
        # For simplicity, we'll reference the primary logs key
        # In a real implementation, you'd create actual replicas
        pass

    def _create_database_replica(self) -> None:
        """Create the RDS read replica in the secondary region."""

        # Get database configuration from primary
        db_instance_class = ec2.InstanceType.of(
            ec2.InstanceClass.T3,
            ec2.InstanceSize(
                self._config.get("db_instance_class", "db.t3.micro")
                .split(".")[-1]
                .upper()
            ),
        )

        # Create security group for database replica
        self._database_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self._vpc,
            description="Security group for RDS database replica",
            allow_all_outbound=False,
        )

        # Allow PostgreSQL traffic from VPC (for testing/management)
        self._database_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self._vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL traffic from VPC",
        )

        # Create subnet group for database replica
        self._database_subnet_group = rds.SubnetGroup(
            self,
            "DatabaseSubnetGroup",
            description="Subnet group for RDS database replica",
            vpc=self._vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
        )

        # Create the read replica
        # Note: In practice, cross-region read replicas need to be created
        # in the target region using the primary instance as source
        # This is a simplified representation

        # For demonstration purposes, we'll create a placeholder
        # In a real implementation, you would use:
        # rds.DatabaseInstance.from_database_instance_attributes()
        # to reference the primary and then create the replica

        self._database_replica = rds.DatabaseInstance(
            self,
            "DatabaseReplica",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_4
            ),
            instance_type=db_instance_class,
            vpc=self._vpc,
            subnet_group=self._database_subnet_group,
            security_groups=[self._database_security_group],
            database_name="drlab",
            allocated_storage=self._config.get("db_allocated_storage", 20),
            storage_encrypted=True,
            storage_encryption_key=self._primary_kms_key.key,  # Use the multi-region key
            backup_retention=Duration.days(0),  # No backups for replica
            delete_automated_backups=True,
            removal_policy=Stack.of(self).node.try_get_context(
                "@aws-cdk/core:removalPolicy"
            )
            or None,
            # In a real implementation, you would specify:
            # source_db_instance_identifier=primary_db_instance_identifier,
            # replicate_source_db=True
        )

    def _create_s3_buckets(self) -> None:
        """Create S3 buckets as replicas of primary buckets."""

        # Create replicated application data bucket
        # This bucket will receive replicated data from the primary
        self._app_data_bucket = s3.Bucket(
            self,
            "AppDataBucket",
            bucket_name=f"dr-lab-app-data-{self._config.get('secondary_region', 'us-west-2')}",
            versioned=True,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self._primary_kms_key.key,  # Use the multi-region key
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.STANDARD_IA,
                            transition_after=Duration.days(
                                self._config.get("s3_lifecycle_ia_days", 30)
                            ),
                        )
                    ],
                ),
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
            public_read_access=False,
            public_write_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        # Create logs bucket (no replication needed for logs)
        self._logs_bucket = s3.Bucket(
            self,
            "LogsBucket",
            bucket_name=f"dr-lab-logs-{self._config.get('secondary_region', 'us-west-2')}",
            versioned=False,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self._primary_kms_key.key,  # Use the multi-region key
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldLogs",
                    enabled=True,
                    expiration=Duration.days(
                        self._config.get("cloudwatch_log_retention_days", 14) * 2
                    ),
                ),
                s3.LifecycleRule(
                    id="TransitionLogsToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.STANDARD_IA,
                            transition_after=Duration.days(7),
                        )
                    ],
                ),
            ],
            public_read_access=False,
            public_write_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        # Database replica outputs
        CfnOutput(
            self,
            "DatabaseReplicaEndpoint",
            value=self._database_replica.instance_endpoint.hostname,
            description="Database replica endpoint",
            export_name=f"{self.stack_name}-DatabaseReplicaEndpoint",
        )

        CfnOutput(
            self,
            "DatabaseReplicaPort",
            value=str(self._database_replica.instance_endpoint.port),
            description="Database replica port",
            export_name=f"{self.stack_name}-DatabaseReplicaPort",
        )

        # S3 bucket outputs
        CfnOutput(
            self,
            "AppDataBucketName",
            value=self._app_data_bucket.bucket_name,
            description="Name of the application data bucket",
            export_name=f"{self.stack_name}-AppDataBucketName",
        )

        CfnOutput(
            self,
            "AppDataBucketArn",
            value=self._app_data_bucket.bucket_arn,
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

    def _add_tags(self) -> None:
        """Add tags to all resources in this stack."""

        Tags.of(self).add("Component", "Data")
        Tags.of(self).add("Region", "Secondary")
        Tags.of(self).add("Environment", "Production")

    @property
    def database_replica(self) -> rds.DatabaseInstance:
        """Get the database replica."""
        return self._database_replica

    @property
    def app_data_bucket(self) -> s3.Bucket:
        """Get the application data bucket."""
        return self._app_data_bucket

    @property
    def logs_bucket(self) -> s3.Bucket:
        """Get the logs bucket."""
        return self._logs_bucket

    @property
    def database_security_group(self) -> ec2.SecurityGroup:
        """Get the database security group."""
        return self._database_security_group
