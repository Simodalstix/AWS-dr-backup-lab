"""
Secondary App Stack
Creates the warm standby application infrastructure in the secondary region.
"""

from typing import Dict
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_s3 as s3,
    aws_rds as rds,
    aws_logs as logs,
    Duration,
    CfnOutput,
    Tags,
)
from constructs import Construct

from constructs.ecs_service_alb import ECSServiceALB


class SecondaryAppStack(Stack):
    """
    Stack that creates the warm standby application infrastructure for the secondary region.

    This stack creates:
    - ECS cluster
    - ECS Fargate service with warm standby configuration (1 task)
    - Application Load Balancer (standby)
    - Target groups and listeners
    - Auto scaling configuration
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        database: rds.DatabaseInstance,
        s3_bucket: s3.Bucket,
        config: Dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._vpc = vpc
        self._database = database
        self._s3_bucket = s3_bucket
        self._config = config

        # Create ECS cluster
        self._create_ecs_cluster()

        # Create ECS service with ALB (warm standby)
        self._create_ecs_service()

        # Create outputs
        self._create_outputs()

        # Add tags
        self._add_tags()

    def _create_ecs_cluster(self) -> None:
        """Create the ECS cluster."""

        self._cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=self._vpc,
            cluster_name=f"dr-lab-secondary-{self.region}",
            enable_fargate_capacity_providers=True,
            container_insights=True,
        )

        # Capacity providers are automatically enabled with enable_fargate_capacity_providers=True
        # This includes both FARGATE and FARGATE_SPOT capacity providers

    def _create_ecs_service(self) -> None:
        """Create the ECS service with Application Load Balancer (warm standby)."""

        # Prepare environment variables
        environment_variables = {
            "AWS_DEFAULT_REGION": self.region,
            "ENVIRONMENT": "standby",
            "REGION": "secondary",
            "S3_BUCKET": self._s3_bucket.bucket_name,
            "DATABASE_NAME": "drlab",
        }

        # Prepare secrets
        # Note: In a real implementation, you would need to handle secrets differently
        # for the secondary region, possibly using cross-region secret references
        # or replicating secrets. For this implementation, we'll use placeholder values.

        # Get configuration
        container_image = self._config.get("container_image", "nginx:latest")
        container_port = self._config.get("container_port", 80)
        health_check_path = self._config.get("health_check_path", "/healthz")
        ecs_cpu = self._config.get("ecs_cpu", 256)
        ecs_memory = self._config.get("ecs_memory", 512)
        warm_standby_tasks = self._config.get("warm_standby_tasks", 1)

        # Create ECS service with ALB
        self._ecs_service_alb = ECSServiceALB(
            self,
            "ECSService",
            vpc=self._vpc,
            cluster=self._cluster,
            image=container_image,
            port=container_port,
            health_check_path=health_check_path,
            task_count=warm_standby_tasks,  # Warm standby configuration
            min_task_count=0,  # Can scale down to 0 for cost savings
            max_task_count=10,  # Can scale up during failover
            cpu=ecs_cpu,
            memory=ecs_memory,
            environment_variables=environment_variables,
            enable_logging=True,
            log_retention=logs.RetentionDays.TWO_WEEKS,
        )

        # Grant permissions to access S3 bucket
        self._s3_bucket.grant_read_write(self._ecs_service_alb.task_role)

        # Create security group for database access
        # In a real implementation, you would need to handle cross-region database access
        # This is a simplified approach for demonstration purposes

        # Create custom target group for health checks
        self._create_health_check_configuration()

    def _create_health_check_configuration(self) -> None:
        """Configure advanced health check settings."""

        # Get the target group from the ECS service
        target_group = self._ecs_service_alb.target_group

        # Configure health check settings
        cfn_target_group = target_group.node.default_child
        cfn_target_group.health_check_enabled = True
        cfn_target_group.health_check_grace_period_seconds = 60
        cfn_target_group.health_check_interval_seconds = 30
        cfn_target_group.health_check_path = self._config.get(
            "health_check_path", "/healthz"
        )
        cfn_target_group.health_check_port = "traffic-port"
        cfn_target_group.health_check_protocol = "HTTP"
        cfn_target_group.health_check_timeout_seconds = 5
        cfn_target_group.healthy_threshold_count = 2
        cfn_target_group.unhealthy_threshold_count = 3
        cfn_target_group.matcher = {"HttpCode": "200"}

        # Configure deregistration delay
        cfn_target_group.target_group_attributes = [
            {"Key": "deregistration_delay.timeout_seconds", "Value": "30"},
            {"Key": "stickiness.enabled", "Value": "false"},
            {"Key": "load_balancing.algorithm.type", "Value": "round_robin"},
        ]

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        # ECS Cluster outputs
        CfnOutput(
            self,
            "ClusterName",
            value=self._cluster.cluster_name,
            description="Name of the ECS cluster",
            export_name=f"{self.stack_name}-ClusterName",
        )

        CfnOutput(
            self,
            "ClusterArn",
            value=self._cluster.cluster_arn,
            description="ARN of the ECS cluster",
            export_name=f"{self.stack_name}-ClusterArn",
        )

        # Load Balancer outputs
        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self._ecs_service_alb.load_balancer.load_balancer_dns_name,
            description="DNS name of the Application Load Balancer (Standby)",
            export_name=f"{self.stack_name}-LoadBalancerDNS",
        )

        CfnOutput(
            self,
            "LoadBalancerArn",
            value=self._ecs_service_alb.load_balancer.load_balancer_arn,
            description="ARN of the Application Load Balancer (Standby)",
            export_name=f"{self.stack_name}-LoadBalancerArn",
        )

        CfnOutput(
            self,
            "LoadBalancerHostedZoneId",
            value=self._ecs_service_alb.load_balancer.load_balancer_canonical_hosted_zone_id,
            description="Hosted Zone ID of the Application Load Balancer (Standby)",
            export_name=f"{self.stack_name}-LoadBalancerHostedZoneId",
        )

        # ECS Service outputs
        CfnOutput(
            self,
            "ServiceName",
            value=self._ecs_service_alb.service.service_name,
            description="Name of the ECS service",
            export_name=f"{self.stack_name}-ServiceName",
        )

        CfnOutput(
            self,
            "ServiceArn",
            value=self._ecs_service_alb.service.service_arn,
            description="ARN of the ECS service",
            export_name=f"{self.stack_name}-ServiceArn",
        )

        # Target Group outputs
        CfnOutput(
            self,
            "TargetGroupArn",
            value=self._ecs_service_alb.target_group.target_group_arn,
            description="ARN of the target group",
            export_name=f"{self.stack_name}-TargetGroupArn",
        )

        # Application URL (standby)
        CfnOutput(
            self,
            "StandbyApplicationURL",
            value=f"http://{self._ecs_service_alb.load_balancer.load_balancer_dns_name}",
            description="URL of the standby application",
            export_name=f"{self.stack_name}-StandbyApplicationURL",
        )

        # Health Check URL (standby)
        CfnOutput(
            self,
            "StandbyHealthCheckURL",
            value=f"http://{self._ecs_service_alb.load_balancer.load_balancer_dns_name}{self._config.get('health_check_path', '/healthz')}",
            description="Health check URL of the standby application",
            export_name=f"{self.stack_name}-StandbyHealthCheckURL",
        )

    def _add_tags(self) -> None:
        """Add tags to all resources in this stack."""

        Tags.of(self).add("Component", "Application")
        Tags.of(self).add("Region", "Secondary")
        Tags.of(self).add("Environment", "Production")

    @property
    def cluster(self) -> ecs.Cluster:
        """Get the ECS cluster."""
        return self._cluster

    @property
    def ecs_service(self) -> ecs.FargateService:
        """Get the ECS service."""
        return self._ecs_service_alb.service

    @property
    def load_balancer(self) -> "elbv2.ApplicationLoadBalancer":
        """Get the Application Load Balancer."""
        return self._ecs_service_alb.load_balancer

    @property
    def target_group(self) -> "elbv2.ApplicationTargetGroup":
        """Get the target group."""
        return self._ecs_service_alb.target_group

    @property
    def ecs_service_alb(self) -> ECSServiceALB:
        """Get the ECS service with ALB construct."""
        return self._ecs_service_alb
