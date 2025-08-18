"""
Recovery Parameters Construct
SSM parameter management for recovery configuration.
"""

from typing import Dict
from aws_cdk import (
    aws_ssm as ssm,
    Stack,
    CfnOutput,
)
from constructs import Construct


class RecoveryParameters(Construct):
    """
    A construct that manages SSM parameters for recovery configuration.

    This construct provides:
    - Centralized parameter storage for recovery settings
    - Easy parameter retrieval for automation
    - Configuration management across regions
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        primary_region: str,
        secondary_region: str,
        vpc_cidr: str = "10.1.0.0/16",
        availability_zones: int = 2,
        ecs_cpu: int = 256,
        ecs_memory: int = 512,
        container_image: str = "nginx:latest",
        container_port: int = 80,
        template_bucket_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._primary_region = primary_region
        self._secondary_region = secondary_region
        self._template_bucket_name = template_bucket_name

        # Recovery configuration parameters
        self._recovery_config = {
            "vpc_cidr": vpc_cidr,
            "availability_zones": str(availability_zones),
            "ecs_cpu": str(ecs_cpu),
            "ecs_memory": str(ecs_memory),
            "container_image": container_image,
            "container_port": str(container_port),
            "template_bucket": template_bucket_name,
            "primary_region": primary_region,
            "secondary_region": secondary_region,
        }

        # Create SSM parameters
        self._create_parameters()

        # Create outputs
        self._create_outputs()

    def _create_parameters(self) -> None:
        """Create SSM parameters for recovery configuration."""

        self._parameters = {}

        for param_name, param_value in self._recovery_config.items():
            parameter = ssm.StringParameter(
                self,
                f"RecoveryParam{param_name.replace('_', '').title()}",
                parameter_name=f"/dr-lab/recovery/{param_name}",
                string_value=param_value,
                description=f"Recovery configuration parameter: {param_name}",
                tier=ssm.ParameterTier.STANDARD,
            )
            self._parameters[param_name] = parameter

        # Additional operational parameters
        operational_params = {
            "rto_target_minutes": "180",  # 3 hours
            "rpo_target_hours": "4",  # 4 hours
            "backup_retention_days": "30",
            "test_schedule": "cron(0 2 1 * ? *)",  # Monthly
            "validation_schedule": "cron(0 4 ? * SUN *)",  # Weekly
        }

        for param_name, param_value in operational_params.items():
            parameter = ssm.StringParameter(
                self,
                f"OperationalParam{param_name.replace('_', '').title()}",
                parameter_name=f"/dr-lab/operational/{param_name}",
                string_value=param_value,
                description=f"Operational parameter: {param_name}",
                tier=ssm.ParameterTier.STANDARD,
            )
            self._parameters[param_name] = parameter

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "ParameterPathPrefix",
            value="/dr-lab/",
            description="SSM parameter path prefix for DR lab configuration",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-PathPrefix",
        )

        CfnOutput(
            self,
            "RecoveryParameterPath",
            value="/dr-lab/recovery/",
            description="SSM parameter path for recovery configuration",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-RecoveryPath",
        )

        CfnOutput(
            self,
            "OperationalParameterPath",
            value="/dr-lab/operational/",
            description="SSM parameter path for operational configuration",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-OperationalPath",
        )

    @property
    def parameters(self) -> Dict[str, ssm.StringParameter]:
        """Get all created parameters."""
        return self._parameters

    @property
    def recovery_config(self) -> Dict[str, str]:
        """Get the recovery configuration."""
        return self._recovery_config

    def get_parameter(self, param_name: str) -> ssm.StringParameter:
        """Get a specific parameter by name."""
        return self._parameters.get(param_name)

    def get_parameter_name(self, param_name: str) -> str:
        """Get the full parameter name for a given parameter."""
        if param_name in self._recovery_config:
            return f"/dr-lab/recovery/{param_name}"
        else:
            return f"/dr-lab/operational/{param_name}"

    def add_parameter(
        self, param_name: str, param_value: str, description: str = None
    ) -> ssm.StringParameter:
        """Add a new parameter to the recovery configuration."""
        parameter = ssm.StringParameter(
            self,
            f"CustomParam{param_name.replace('_', '').title()}",
            parameter_name=f"/dr-lab/custom/{param_name}",
            string_value=param_value,
            description=description or f"Custom parameter: {param_name}",
            tier=ssm.ParameterTier.STANDARD,
        )
        self._parameters[param_name] = parameter
        return parameter
