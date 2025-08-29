"""
Secrets Manager Construct
Centralized secrets management for the DR Lab application.
"""

from typing import Dict, Optional

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_secretsmanager as secretsmanager

from constructs import Construct


class SecretsManager(Construct):
    """
    A construct that creates and manages application secrets using AWS Secrets Manager.

    This construct provides:
    - Centralized secret storage with KMS encryption
    - Automatic rotation capabilities
    - IAM-based access control
    - Cross-region secret replication
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        kms_key: kms.IKey,
        replica_regions: Optional[list] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._kms_key = kms_key
        self._replica_regions = replica_regions or []
        self._secrets = {}

        # Create application configuration secret
        self._create_app_config_secret()

        # Create database credentials secret (separate from RDS-managed)
        self._create_database_config_secret()

        # Create API keys secret
        self._create_api_keys_secret()

        # Create outputs
        self._create_outputs()

    def _create_app_config_secret(self) -> None:
        """Create secret for application configuration."""

        app_config = {
            "environment": "production",
            "log_level": "INFO",
            "feature_flags": {
                "enable_backup_validation": True,
                "enable_cross_region_replication": True,
                "enable_monitoring": True,
            },
            "backup_settings": {
                "retention_days": 30,
                "backup_window": "03:00-04:00",
                "maintenance_window": "sun:04:00-sun:05:00",
            },
        }

        self._app_config_secret = secretsmanager.Secret(
            self,
            "AppConfigSecret",
            secret_name="dr-lab/app-config",
            description="Application configuration for DR Lab",
            encryption_key=self._kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=str(app_config).replace("'", '"'),
                generate_string_key="generated_config",
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
            ),
            replica_regions=self._get_replica_regions(),
            removal_policy=RemovalPolicy.DESTROY,  # For lab purposes
        )

        self._secrets["app_config"] = self._app_config_secret

    def _create_database_config_secret(self) -> None:
        """Create secret for database configuration (non-credential data)."""

        self._db_config_secret = secretsmanager.Secret(
            self,
            "DatabaseConfigSecret",
            secret_name="dr-lab/database-config",
            description="Database configuration for DR Lab (non-sensitive)",
            encryption_key=self._kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"database_name": "drlab", "port": "5433", "engine": "postgres", "engine_version": "15.4", "parameter_group_family": "postgres15", "backup_retention_period": "7", "backup_window": "03:00-04:00", "maintenance_window": "sun:04:00-sun:05:00"}',
                generate_string_key="config_version",
                password_length=8,
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
            ),
            replica_regions=self._get_replica_regions(),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self._secrets["database_config"] = self._db_config_secret

    def _create_api_keys_secret(self) -> None:
        """Create secret for API keys and external service credentials."""

        self._api_keys_secret = secretsmanager.Secret(
            self,
            "ApiKeysSecret",
            secret_name="dr-lab/api-keys",
            description="API keys and external service credentials",
            encryption_key=self._kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"monitoring_api_key": "PLACEHOLDER", "notification_webhook": "PLACEHOLDER"}',
                generate_string_key="external_api_key",
                password_length=32,
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
            ),
            replica_regions=self._get_replica_regions(),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self._secrets["api_keys"] = self._api_keys_secret

    def _get_replica_regions(self) -> list:
        """Get replica regions configuration for secrets."""
        replica_configs = []
        for region in self._replica_regions:
            replica_configs.append(
                secretsmanager.ReplicaRegion(
                    region=region,
                    encryption_key=self._kms_key,  # Multi-region key works across regions
                )
            )
        return replica_configs

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "AppConfigSecretArn",
            value=self._app_config_secret.secret_arn,
            description="ARN of the application configuration secret",
            export_name=f"{Stack.of(self).stack_name}-AppConfigSecretArn",
        )

        CfnOutput(
            self,
            "DatabaseConfigSecretArn",
            value=self._db_config_secret.secret_arn,
            description="ARN of the database configuration secret",
            export_name=f"{Stack.of(self).stack_name}-DatabaseConfigSecretArn",
        )

        CfnOutput(
            self,
            "ApiKeysSecretArn",
            value=self._api_keys_secret.secret_arn,
            description="ARN of the API keys secret",
            export_name=f"{Stack.of(self).stack_name}-ApiKeysSecretArn",
        )

    def grant_read_access(self, grantee: iam.IGrantable, secret_name: str) -> iam.Grant:
        """Grant read access to a specific secret."""
        if secret_name not in self._secrets:
            raise ValueError(f"Secret '{secret_name}' not found")

        return self._secrets[secret_name].grant_read(grantee)

    def grant_read_all_secrets(self, grantee: iam.IGrantable) -> list:
        """Grant read access to all secrets."""
        grants = []
        for secret in self._secrets.values():
            grants.append(secret.grant_read(grantee))
        return grants

    @property
    def app_config_secret(self) -> secretsmanager.Secret:
        """Get the application configuration secret."""
        return self._app_config_secret

    @property
    def database_config_secret(self) -> secretsmanager.Secret:
        """Get the database configuration secret."""
        return self._db_config_secret

    @property
    def api_keys_secret(self) -> secretsmanager.Secret:
        """Get the API keys secret."""
        return self._api_keys_secret

    def get_secret(self, secret_name: str) -> secretsmanager.Secret:
        """Get a specific secret by name."""
        if secret_name not in self._secrets:
            raise ValueError(f"Secret '{secret_name}' not found")
        return self._secrets[secret_name]
