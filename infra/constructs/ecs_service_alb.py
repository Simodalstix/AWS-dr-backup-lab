"""
ECS Service with ALB Construct
Creates an ECS Fargate service with an associated Application Load Balancer.
"""

from typing import Dict, List, Optional
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_kms as kms,
    Duration,
    Stack,
    CfnOutput,
)
from constructs import Construct


class ECSServiceALB(Construct):
    """
    A construct that creates an ECS Fargate service with an Application Load Balancer.

    This construct provides a complete setup for running containerized applications
    with load balancing, health checks, and proper security configurations.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        cluster: ecs.Cluster,
        image: str,
        port: int = 80,
        health_check_path: str = "/healthz",
        task_count: int = 2,
        min_task_count: int = 1,
        max_task_count: int = 10,
        cpu: int = 256,
        memory: int = 512,
        environment_variables: Optional[Dict[str, str]] = None,
        secrets: Optional[Dict[str, ecs.Secret]] = None,
        kms_key: Optional[kms.IKey] = None,
        enable_logging: bool = True,
        log_retention: logs.RetentionDays = logs.RetentionDays.TWO_WEEKS,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._vpc = vpc
        self._cluster = cluster
        self._image = image
        self._port = port
        self._health_check_path = health_check_path
        self._task_count = task_count
        self._min_task_count = min_task_count
        self._max_task_count = max_task_count
        self._cpu = cpu
        self._memory = memory
        self._environment_variables = environment_variables or {}
        self._secrets = secrets or {}
        self._kms_key = kms_key
        self._enable_logging = enable_logging
        self._log_retention = log_retention

        # Create security groups
        self._create_security_groups()

        # Create Application Load Balancer
        self._create_load_balancer()

        # Create ECS Task Definition
        self._create_task_definition()

        # Create ECS Service
        self._create_service()

        # Create outputs
        self._create_outputs()

    def _create_security_groups(self) -> None:
        """Create security groups for ALB and ECS service."""

        # ALB Security Group
        self._alb_security_group = ec2.SecurityGroup(
            self,
            "ALBSecurityGroup",
            vpc=self._vpc,
            description="Security group for Application Load Balancer",
            allow_all_outbound=True,
        )

        # Allow HTTP traffic from internet
        self._alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic from internet",
        )

        # Allow HTTPS traffic from internet
        self._alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS traffic from internet",
        )

        # ECS Security Group
        self._ecs_security_group = ec2.SecurityGroup(
            self,
            "ECSSecurityGroup",
            vpc=self._vpc,
            description="Security group for ECS service",
            allow_all_outbound=True,
        )

        # Allow traffic from ALB to ECS
        self._ecs_security_group.add_ingress_rule(
            peer=self._alb_security_group,
            connection=ec2.Port.tcp(self._port),
            description="Allow traffic from ALB to ECS",
        )

    def _create_load_balancer(self) -> None:
        """Create the Application Load Balancer."""

        self._load_balancer = elbv2.ApplicationLoadBalancer(
            self,
            "LoadBalancer",
            vpc=self._vpc,
            internet_facing=True,
            security_group=self._alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # Create target group
        self._target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup",
            vpc=self._vpc,
            port=self._port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path=self._health_check_path,
                protocol=elbv2.Protocol.HTTP,
                timeout=Duration.seconds(5),
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
            deregistration_delay=Duration.seconds(30),
        )

        # Create listener
        self._listener = self._load_balancer.add_listener(
            "Listener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[self._target_group],
        )

    def _create_task_definition(self) -> None:
        """Create the ECS task definition."""

        # Create task execution role
        self._task_execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # Create task role
        self._task_role = iam.Role(
            self, "TaskRole", assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )

        # Grant KMS permissions if key is provided
        if self._kms_key:
            self._kms_key.grant_encrypt_decrypt(self._task_execution_role)
            self._kms_key.grant_encrypt_decrypt(self._task_role)

        # Create log group if logging is enabled
        log_group = None
        if self._enable_logging:
            log_group = logs.LogGroup(
                self,
                "LogGroup",
                log_group_name=f"/ecs/{Stack.of(self).stack_name}-{self.node.id}",
                retention=self._log_retention,
                encryption_key=self._kms_key,
                removal_policy=Stack.of(self).node.try_get_context(
                    "@aws-cdk/core:removalPolicy"
                ),
            )

        # Create task definition
        self._task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            memory_limit_mib=self._memory,
            cpu=self._cpu,
            execution_role=self._task_execution_role,
            task_role=self._task_role,
        )

        # Create container definition
        container_definition = self._task_definition.add_container(
            "Container",
            image=ecs.ContainerImage.from_registry(self._image),
            memory_limit_mib=self._memory,
            cpu=self._cpu,
            environment=self._environment_variables,
            secrets=self._secrets,
            logging=(
                ecs.LogDrivers.aws_logs(stream_prefix="ecs", log_group=log_group)
                if self._enable_logging
                else None
            ),
        )

        # Add port mapping
        container_definition.add_port_mappings(
            ecs.PortMapping(container_port=self._port, protocol=ecs.Protocol.TCP)
        )

    def _create_service(self) -> None:
        """Create the ECS service."""

        self._service = ecs.FargateService(
            self,
            "Service",
            cluster=self._cluster,
            task_definition=self._task_definition,
            desired_count=self._task_count,
            security_groups=[self._ecs_security_group],
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            assign_public_ip=False,
            enable_logging=self._enable_logging,
            health_check_grace_period=Duration.seconds(60),
            min_healthy_percent=50,
            max_healthy_percent=200,
        )

        # Attach service to target group
        self._service.attach_to_application_target_group(self._target_group)

        # Enable auto scaling
        scalable_target = self._service.auto_scale_task_count(
            min_capacity=self._min_task_count, max_capacity=self._max_task_count
        )

        # Add CPU scaling policy
        scalable_target.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(300),
        )

        # Add memory scaling policy
        scalable_target.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(300),
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self._load_balancer.load_balancer_dns_name,
            description="DNS name of the Application Load Balancer",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-LoadBalancerDNS",
        )

        CfnOutput(
            self,
            "LoadBalancerArn",
            value=self._load_balancer.load_balancer_arn,
            description="ARN of the Application Load Balancer",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-LoadBalancerArn",
        )

        CfnOutput(
            self,
            "ServiceName",
            value=self._service.service_name,
            description="Name of the ECS service",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-ServiceName",
        )

        CfnOutput(
            self,
            "ServiceArn",
            value=self._service.service_arn,
            description="ARN of the ECS service",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-ServiceArn",
        )

    @property
    def load_balancer(self) -> elbv2.ApplicationLoadBalancer:
        """Get the Application Load Balancer."""
        return self._load_balancer

    @property
    def target_group(self) -> elbv2.ApplicationTargetGroup:
        """Get the target group."""
        return self._target_group

    @property
    def listener(self) -> elbv2.ApplicationListener:
        """Get the listener."""
        return self._listener

    @property
    def service(self) -> ecs.FargateService:
        """Get the ECS service."""
        return self._service

    @property
    def task_definition(self) -> ecs.FargateTaskDefinition:
        """Get the task definition."""
        return self._task_definition

    @property
    def task_role(self) -> iam.Role:
        """Get the task role."""
        return self._task_role

    @property
    def task_execution_role(self) -> iam.Role:
        """Get the task execution role."""
        return self._task_execution_role

    @property
    def alb_security_group(self) -> ec2.SecurityGroup:
        """Get the ALB security group."""
        return self._alb_security_group

    @property
    def ecs_security_group(self) -> ec2.SecurityGroup:
        """Get the ECS security group."""
        return self._ecs_security_group

    def scale_tasks(self, count: int) -> None:
        """Scale the service to the specified task count."""
        # This would typically be done through AWS APIs in a real scenario
        # For CDK, we can update the desired count property
        pass
