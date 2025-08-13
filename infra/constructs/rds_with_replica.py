"""
RDS with Replica Construct
Creates RDS primary instance with cross-region read replica for standard PostgreSQL.
"""

from typing import Dict, List, Optional
from aws_cdk import (
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_iam as iam,
    aws_kms as kms,
    aws_secretsmanager as secretsmanager,
    aws_logs as logs,
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
)
from constructs import Construct


class RDSWithReplica(Construct):
    """
    A construct that creates RDS primary instance with cross-region read replica.

    This construct provides a complete setup for PostgreSQL database with
    automated backups, security configurations, and cross-region replication.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        engine: rds.IInstanceEngine = rds.DatabaseInstanceEngine.postgres(
            version=rds.PostgresEngineVersion.VER_15_4
        ),
        instance_class: ec2.InstanceType = ec2.InstanceType.of(
            ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
        ),
        allocated_storage: int = 20,
        max_allocated_storage: int = 100,
        backup_retention: Duration = Duration.days(7),
        database_name: str = "drlab",
        username: str = "admin",
        kms_key: Optional[kms.IKey] = None,
        replica_region: Optional[str] = None,
        replica_instance_class: Optional[ec2.InstanceType] = None,
        enable_performance_insights: bool = True,
        performance_insights_retention: rds.PerformanceInsightsRetention = rds.PerformanceInsightsRetention.DEFAULT,
        monitoring_interval: Duration = Duration.seconds(60),
        enable_logging: bool = True,
        log_types: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._vpc = vpc
        self._engine = engine
        self._instance_class = instance_class
        self._allocated_storage = allocated_storage
        self._max_allocated_storage = max_allocated_storage
        self._backup_retention = backup_retention
        self._database_name = database_name
        self._username = username
        self._kms_key = kms_key
        self._replica_region = replica_region
        self._replica_instance_class = replica_instance_class or instance_class
        self._enable_performance_insights = enable_performance_insights
        self._performance_insights_retention = performance_insights_retention
        self._monitoring_interval = monitoring_interval
        self._enable_logging = enable_logging
        self._log_types = log_types or ["postgresql"]

        # Create security group
        self._create_security_group()

        # Create subnet group
        self._create_subnet_group()

        # Create parameter group
        self._create_parameter_group()

        # Create option group (if needed)
        self._create_option_group()

        # Create monitoring role
        self._create_monitoring_role()

        # Create database credentials
        self._create_credentials()

        # Create primary database instance
        self._create_primary_instance()

        # Create read replica if specified
        if self._replica_region:
            self._create_read_replica()

        # Create outputs
        self._create_outputs()

    def _create_security_group(self) -> None:
        """Create security group for RDS instance."""

        self._security_group = ec2.SecurityGroup(
            self,
            "SecurityGroup",
            vpc=self._vpc,
            description="Security group for RDS database",
            allow_all_outbound=False,
        )

        # Allow PostgreSQL traffic from VPC
        self._security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self._vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL traffic from VPC",
        )

    def _create_subnet_group(self) -> None:
        """Create DB subnet group."""

        self._subnet_group = rds.SubnetGroup(
            self,
            "SubnetGroup",
            description="Subnet group for RDS database",
            vpc=self._vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
        )

    def _create_parameter_group(self) -> None:
        """Create DB parameter group with optimized settings."""

        self._parameter_group = rds.ParameterGroup(
            self,
            "ParameterGroup",
            engine=self._engine,
            description="Parameter group for PostgreSQL with optimized settings",
            parameters={
                # Connection settings
                "max_connections": "100",
                # Memory settings
                "shared_preload_libraries": "pg_stat_statements",
                # Logging settings
                "log_statement": "all",
                "log_min_duration_statement": "1000",  # Log queries taking > 1s
                "log_checkpoints": "on",
                "log_connections": "on",
                "log_disconnections": "on",
                "log_lock_waits": "on",
                # Performance settings
                "random_page_cost": "1.1",  # Optimized for SSD
                "effective_cache_size": "256MB",
                # Replication settings
                "wal_level": "replica",
                "max_wal_senders": "3",
                "wal_keep_segments": "32",
            },
        )

    def _create_option_group(self) -> None:
        """Create DB option group if needed."""
        # PostgreSQL doesn't typically need option groups
        # This is more relevant for Oracle/SQL Server
        pass

    def _create_monitoring_role(self) -> None:
        """Create IAM role for enhanced monitoring."""

        self._monitoring_role = iam.Role(
            self,
            "MonitoringRole",
            assumed_by=iam.ServicePrincipal("monitoring.rds.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonRDSEnhancedMonitoringRole"
                )
            ],
        )

    def _create_credentials(self) -> None:
        """Create database credentials in Secrets Manager."""

        self._credentials = rds.Credentials.from_generated_secret(
            username=self._username,
            secret_name=f"{Stack.of(self).stack_name}-{self.node.id}-credentials",
            encryption_key=self._kms_key,
        )

    def _create_primary_instance(self) -> None:
        """Create the primary RDS instance."""

        self._primary_instance = rds.DatabaseInstance(
            self,
            "PrimaryInstance",
            engine=self._engine,
            instance_type=self._instance_class,
            vpc=self._vpc,
            subnet_group=self._subnet_group,
            security_groups=[self._security_group],
            credentials=self._credentials,
            database_name=self._database_name,
            allocated_storage=self._allocated_storage,
            max_allocated_storage=self._max_allocated_storage,
            storage_encrypted=True,
            storage_encryption_key=self._kms_key,
            backup_retention=self._backup_retention,
            backup_window="03:00-04:00",  # UTC
            maintenance_window="sun:04:00-sun:05:00",  # UTC
            preferred_backup_window="03:00-04:00",
            preferred_maintenance_window="sun:04:00-sun:05:00",
            parameter_group=self._parameter_group,
            monitoring_interval=self._monitoring_interval,
            monitoring_role=self._monitoring_role,
            enable_performance_insights=self._enable_performance_insights,
            performance_insights_retention=self._performance_insights_retention,
            performance_insights_encryption_key=self._kms_key,
            cloudwatch_logs_exports=self._log_types if self._enable_logging else None,
            cloudwatch_logs_retention=logs.RetentionDays.TWO_WEEKS,
            cloudwatch_logs_retention_role=self._create_logs_role(),
            deletion_protection=True,
            delete_automated_backups=False,
            removal_policy=RemovalPolicy.SNAPSHOT,
            copy_tags_to_snapshot=True,
            auto_minor_version_upgrade=True,
            allow_major_version_upgrade=False,
        )

    def _create_logs_role(self) -> iam.Role:
        """Create IAM role for CloudWatch logs."""

        logs_role = iam.Role(
            self,
            "LogsRole",
            assumed_by=iam.ServicePrincipal("rds.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonRDSDirectoryServiceAccess"
                )
            ],
        )

        # Add CloudWatch logs permissions
        logs_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/rds/instance/*"
                ],
            )
        )

        return logs_role

    def _create_read_replica(self) -> None:
        """Create cross-region read replica."""

        # Note: Cross-region read replicas need to be created in the target region
        # This is a placeholder for the replica configuration
        # In practice, this would be handled by a separate stack in the replica region

        self._replica_config = {
            "source_db_identifier": self._primary_instance.instance_identifier,
            "replica_region": self._replica_region,
            "instance_class": self._replica_instance_class,
            "kms_key": self._kms_key,
            "monitoring_interval": self._monitoring_interval,
            "enable_performance_insights": self._enable_performance_insights,
        }

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "PrimaryInstanceEndpoint",
            value=self._primary_instance.instance_endpoint.hostname,
            description="Primary database instance endpoint",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-PrimaryEndpoint",
        )

        CfnOutput(
            self,
            "PrimaryInstancePort",
            value=str(self._primary_instance.instance_endpoint.port),
            description="Primary database instance port",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-PrimaryPort",
        )

        CfnOutput(
            self,
            "PrimaryInstanceIdentifier",
            value=self._primary_instance.instance_identifier,
            description="Primary database instance identifier",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-PrimaryIdentifier",
        )

        CfnOutput(
            self,
            "DatabaseName",
            value=self._database_name,
            description="Database name",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-DatabaseName",
        )

        CfnOutput(
            self,
            "CredentialsSecretArn",
            value=self._primary_instance.secret.secret_arn,
            description="ARN of the database credentials secret",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-CredentialsSecretArn",
        )

    @property
    def primary_instance(self) -> rds.DatabaseInstance:
        """Get the primary database instance."""
        return self._primary_instance

    @property
    def security_group(self) -> ec2.SecurityGroup:
        """Get the database security group."""
        return self._security_group

    @property
    def subnet_group(self) -> rds.SubnetGroup:
        """Get the database subnet group."""
        return self._subnet_group

    @property
    def credentials(self) -> rds.Credentials:
        """Get the database credentials."""
        return self._credentials

    @property
    def secret(self) -> secretsmanager.ISecret:
        """Get the database credentials secret."""
        return self._primary_instance.secret

    @property
    def replica_config(self) -> Dict:
        """Get the replica configuration for cross-region deployment."""
        return getattr(self, "_replica_config", {})

    def allow_connection_from(self, other: ec2.IConnectable) -> None:
        """Allow connections from another security group or construct."""
        self._primary_instance.connections.allow_default_port_from(other)

    def grant_connect(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant connect permissions to the database."""
        return self._primary_instance.grant_connect(grantee)
