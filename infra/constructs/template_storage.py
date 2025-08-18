"""
Template Storage Construct
S3 bucket and deployment logic for CloudFormation templates.
"""

from typing import Dict, List
from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
)
from constructs import Construct


class TemplateStorage(Construct):
    """
    A construct that creates S3 storage for CloudFormation templates.

    This construct provides:
    - S3 bucket for storing recovery templates
    - Automated deployment of template files
    - Versioning and lifecycle management
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        region: str,
        template_files: List[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._region = region
        self._template_files = template_files or [
            "network-template.json",
            "application-template.json",
        ]

        # Create template storage bucket
        self._create_template_bucket()

        # Deploy template files
        self._deploy_templates()

        # Create outputs
        self._create_outputs()

    def _create_template_bucket(self) -> None:
        """Create S3 bucket for storing CloudFormation templates."""

        self._template_bucket = s3.Bucket(
            self,
            "TemplatesBucket",
            bucket_name=f"dr-lab-recovery-templates-{self._region}-{Stack.of(self).account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldVersions",
                    enabled=True,
                    noncurrent_version_expiration=Duration.days(30),
                )
            ],
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _deploy_templates(self) -> None:
        """Deploy CloudFormation templates to S3 bucket."""

        # Deploy templates from local files
        self._template_deployment = s3deploy.BucketDeployment(
            self,
            "TemplateDeployment",
            sources=[s3deploy.Source.asset("templates")],
            destination_bucket=self._template_bucket,
            destination_key_prefix="templates/",
            prune=True,  # Remove files not in source
            retain_on_delete=False,
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "TemplateBucketName",
            value=self._template_bucket.bucket_name,
            description="Name of the recovery templates bucket",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-BucketName",
        )

        CfnOutput(
            self,
            "TemplateBucketArn",
            value=self._template_bucket.bucket_arn,
            description="ARN of the recovery templates bucket",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-BucketArn",
        )

        # Template URLs
        for template_file in self._template_files:
            template_name = (
                template_file.replace("-template.json", "").replace("-", "_").title()
            )
            CfnOutput(
                self,
                f"{template_name}TemplateUrl",
                value=f"https://{self._template_bucket.bucket_name}.s3.amazonaws.com/templates/{template_file}",
                description=f"URL of the {template_name.lower()} recovery template",
                export_name=f"{Stack.of(self).stack_name}-{self.node.id}-{template_name}Url",
            )

    @property
    def template_bucket(self) -> s3.Bucket:
        """Get the template storage bucket."""
        return self._template_bucket

    @property
    def bucket_name(self) -> str:
        """Get the bucket name."""
        return self._template_bucket.bucket_name

    @property
    def bucket_arn(self) -> str:
        """Get the bucket ARN."""
        return self._template_bucket.bucket_arn

    def get_template_url(self, template_name: str) -> str:
        """Get the URL for a specific template."""
        return f"https://{self._template_bucket.bucket_name}.s3.amazonaws.com/templates/{template_name}"

    def add_template_file(self, template_name: str) -> None:
        """Add a new template file to the deployment."""
        if template_name not in self._template_files:
            self._template_files.append(template_name)
