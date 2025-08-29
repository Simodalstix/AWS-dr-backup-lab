"""
KMS Multi-Region Key Construct
Creates and manages multi-region KMS keys for encryption across regions.
"""

from typing import Dict, List, Optional

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms

from constructs import Construct


class KMSMultiRegionKey(Construct):
    """
    A construct that creates a multi-region KMS key for cross-region encryption.

    This construct creates a primary KMS key in the current region and enables
    multi-region functionality for replication to other regions.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        alias: str,
        description: str,
        enable_key_rotation: bool = True,
        replica_regions: Optional[List[str]] = None,
        additional_principals: Optional[List[iam.IPrincipal]] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._alias = alias
        self._description = description
        self._enable_key_rotation = enable_key_rotation
        self._replica_regions = replica_regions or []
        self._additional_principals = additional_principals or []

        # Create the multi-region KMS key
        self._create_key()

        # Create alias
        self._create_alias()

        # Output key information
        self._create_outputs()

    def _create_key(self) -> None:
        """Create the multi-region KMS key with appropriate policies."""

        # Get current account and region
        account = Stack.of(self).account
        region = Stack.of(self).region

        # Create key policy
        key_policy = iam.PolicyDocument(
            statements=[
                # Root account permissions
                iam.PolicyStatement(
                    sid="EnableRootPermissions",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AccountRootPrincipal()],
                    actions=["kms:*"],
                    resources=["*"],
                ),
                # CloudWatch Logs permissions
                iam.PolicyStatement(
                    sid="AllowCloudWatchLogs",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal(f"logs.{region}.amazonaws.com")],
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                    conditions={
                        "ArnEquals": {
                            "kms:EncryptionContext:aws:logs:arn": f"arn:aws:logs:{region}:{account}:*"
                        }
                    },
                ),
                # S3 service permissions
                iam.PolicyStatement(
                    sid="AllowS3Service",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                ),
                # RDS service permissions
                iam.PolicyStatement(
                    sid="AllowRDSService",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("rds.amazonaws.com")],
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                ),
                # ECS service permissions
                iam.PolicyStatement(
                    sid="AllowECSService",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("ecs.amazonaws.com")],
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                ),
            ]
        )

        # Add permissions for additional principals
        if self._additional_principals:
            key_policy.add_statements(
                iam.PolicyStatement(
                    sid="AllowAdditionalPrincipals",
                    effect=iam.Effect.ALLOW,
                    principals=self._additional_principals,
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                )
            )

        # Create the multi-region key
        self._key = kms.Key(
            self,
            "Key",
            description=self._description,
            enable_key_rotation=self._enable_key_rotation,
            policy=key_policy,
            multi_region=True,  # Enable multi-region functionality
            removal_policy=Stack.of(self).node.try_get_context(
                "@aws-cdk/core:removalPolicy"
            )
            or None,
        )

    def _create_alias(self) -> None:
        """Create an alias for the KMS key."""
        self._alias_obj = kms.Alias(
            self, "Alias", alias_name=f"alias/{self._alias}", target_key=self._key
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for the key."""
        CfnOutput(
            self,
            "KeyId",
            value=self._key.key_id,
            description=f"KMS Key ID for {self._alias}",
            export_name=f"{Stack.of(self).stack_name}-{self._alias}-KeyId",
        )

        CfnOutput(
            self,
            "KeyArn",
            value=self._key.key_arn,
            description=f"KMS Key ARN for {self._alias}",
            export_name=f"{Stack.of(self).stack_name}-{self._alias}-KeyArn",
        )

        CfnOutput(
            self,
            "AliasName",
            value=self._alias_obj.alias_name,
            description=f"KMS Key Alias for {self._alias}",
            export_name=f"{Stack.of(self).stack_name}-{self._alias}-AliasName",
        )

    @property
    def key(self) -> kms.Key:
        """Get the KMS key."""
        return self._key

    @property
    def key_id(self) -> str:
        """Get the KMS key ID."""
        return self._key.key_id

    @property
    def key_arn(self) -> str:
        """Get the KMS key ARN."""
        return self._key.key_arn

    @property
    def alias(self) -> kms.Alias:
        """Get the KMS key alias."""
        return self._alias_obj

    def grant_encrypt_decrypt(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant encrypt/decrypt permissions to a principal."""
        return self._key.grant_encrypt_decrypt(grantee)

    def grant_encrypt(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant encrypt permissions to a principal."""
        return self._key.grant_encrypt(grantee)

    def grant_decrypt(self, grantee: iam.IGrantable) -> iam.Grant:
        """Grant decrypt permissions to a principal."""
        return self._key.grant_decrypt(grantee)

    def add_to_resource_policy(
        self, statement: iam.PolicyStatement
    ) -> iam.AddToResourcePolicyResult:
        """Add a statement to the key's resource policy."""
        return self._key.add_to_resource_policy(statement)
