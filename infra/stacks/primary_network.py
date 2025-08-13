"""
Primary Network Stack
Creates the foundational network infrastructure in the primary region.
"""

from typing import Dict, List, Optional
from aws_cdk import Stack, aws_ec2 as ec2, CfnOutput, Tags
from constructs import Construct


class PrimaryNetworkStack(Stack):
    """
    Stack that creates the network infrastructure for the primary region.

    This stack creates:
    - VPC with 2 Availability Zones
    - Public and private subnets in each AZ
    - Internet Gateway
    - NAT Gateways in each AZ
    - Route tables and associations
    - Security groups for different tiers
    """

    def __init__(
        self, scope: Construct, construct_id: str, *, config: Dict, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._config = config

        # Create VPC
        self._create_vpc()

        # Create security groups
        self._create_security_groups()

        # Create VPC endpoints for cost optimization
        self._create_vpc_endpoints()

        # Create outputs
        self._create_outputs()

        # Add tags
        self._add_tags()

    def _create_vpc(self) -> None:
        """Create the VPC with public and private subnets."""

        # Get configuration
        vpc_cidr = self._config.get("vpc_cidr", "10.0.0.0/16")
        availability_zones = self._config.get("availability_zones", 2)
        nat_gateways = self._config.get("nat_gateways", 2)

        # Create VPC
        self._vpc = ec2.Vpc(
            self,
            "VPC",
            ip_addresses=ec2.IpAddresses.cidr(vpc_cidr),
            max_azs=availability_zones,
            nat_gateways=nat_gateways,
            subnet_configuration=[
                # Public subnets for ALB and NAT Gateways
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                # Private subnets for ECS tasks
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                # Isolated subnets for databases
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # Add flow logs for monitoring
        self._vpc.add_flow_log(
            "FlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )

    def _create_security_groups(self) -> None:
        """Create security groups for different application tiers."""

        # ALB Security Group
        self._alb_security_group = ec2.SecurityGroup(
            self,
            "ALBSecurityGroup",
            vpc=self._vpc,
            description="Security group for Application Load Balancer",
            allow_all_outbound=True,
        )

        # Allow HTTP and HTTPS from internet
        self._alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic from internet",
        )

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
            description="Security group for ECS tasks",
            allow_all_outbound=True,
        )

        # Allow traffic from ALB to ECS
        self._ecs_security_group.add_ingress_rule(
            peer=self._alb_security_group,
            connection=ec2.Port.tcp(80),
            description="Allow traffic from ALB to ECS",
        )

        # Database Security Group
        self._database_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self._vpc,
            description="Security group for RDS database",
            allow_all_outbound=False,
        )

        # Allow PostgreSQL traffic from ECS
        self._database_security_group.add_ingress_rule(
            peer=self._ecs_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL traffic from ECS",
        )

        # VPC Endpoint Security Group
        self._vpc_endpoint_security_group = ec2.SecurityGroup(
            self,
            "VPCEndpointSecurityGroup",
            vpc=self._vpc,
            description="Security group for VPC endpoints",
            allow_all_outbound=False,
        )

        # Allow HTTPS traffic from VPC
        self._vpc_endpoint_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self._vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS traffic from VPC",
        )

    def _create_vpc_endpoints(self) -> None:
        """Create VPC endpoints for AWS services to reduce NAT Gateway costs."""

        # S3 Gateway Endpoint
        self._vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            ],
        )

        # DynamoDB Gateway Endpoint
        self._vpc.add_gateway_endpoint(
            "DynamoDBEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            ],
        )

        # ECR API Interface Endpoint
        self._vpc.add_interface_endpoint(
            "ECRAPIEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
            security_groups=[self._vpc_endpoint_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # ECR Docker Interface Endpoint
        self._vpc.add_interface_endpoint(
            "ECRDockerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            security_groups=[self._vpc_endpoint_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # CloudWatch Logs Interface Endpoint
        self._vpc.add_interface_endpoint(
            "CloudWatchLogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            security_groups=[self._vpc_endpoint_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # Secrets Manager Interface Endpoint
        self._vpc.add_interface_endpoint(
            "SecretsManagerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            security_groups=[self._vpc_endpoint_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # KMS Interface Endpoint
        self._vpc.add_interface_endpoint(
            "KMSEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.KMS,
            security_groups=[self._vpc_endpoint_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "VPCId",
            value=self._vpc.vpc_id,
            description="ID of the VPC",
            export_name=f"{self.stack_name}-VPCId",
        )

        CfnOutput(
            self,
            "VPCCidr",
            value=self._vpc.vpc_cidr_block,
            description="CIDR block of the VPC",
            export_name=f"{self.stack_name}-VPCCidr",
        )

        # Public subnet IDs
        public_subnet_ids = [subnet.subnet_id for subnet in self._vpc.public_subnets]
        CfnOutput(
            self,
            "PublicSubnetIds",
            value=",".join(public_subnet_ids),
            description="IDs of the public subnets",
            export_name=f"{self.stack_name}-PublicSubnetIds",
        )

        # Private subnet IDs
        private_subnet_ids = [subnet.subnet_id for subnet in self._vpc.private_subnets]
        CfnOutput(
            self,
            "PrivateSubnetIds",
            value=",".join(private_subnet_ids),
            description="IDs of the private subnets",
            export_name=f"{self.stack_name}-PrivateSubnetIds",
        )

        # Isolated subnet IDs
        isolated_subnet_ids = [
            subnet.subnet_id for subnet in self._vpc.isolated_subnets
        ]
        CfnOutput(
            self,
            "IsolatedSubnetIds",
            value=",".join(isolated_subnet_ids),
            description="IDs of the isolated subnets",
            export_name=f"{self.stack_name}-IsolatedSubnetIds",
        )

        # Security Group IDs
        CfnOutput(
            self,
            "ALBSecurityGroupId",
            value=self._alb_security_group.security_group_id,
            description="ID of the ALB security group",
            export_name=f"{self.stack_name}-ALBSecurityGroupId",
        )

        CfnOutput(
            self,
            "ECSSecurityGroupId",
            value=self._ecs_security_group.security_group_id,
            description="ID of the ECS security group",
            export_name=f"{self.stack_name}-ECSSecurityGroupId",
        )

        CfnOutput(
            self,
            "DatabaseSecurityGroupId",
            value=self._database_security_group.security_group_id,
            description="ID of the database security group",
            export_name=f"{self.stack_name}-DatabaseSecurityGroupId",
        )

    def _add_tags(self) -> None:
        """Add tags to all resources in this stack."""

        Tags.of(self).add("Component", "Network")
        Tags.of(self).add("Region", "Primary")
        Tags.of(self).add("Environment", "Production")

    @property
    def vpc(self) -> ec2.Vpc:
        """Get the VPC."""
        return self._vpc

    @property
    def alb_security_group(self) -> ec2.SecurityGroup:
        """Get the ALB security group."""
        return self._alb_security_group

    @property
    def ecs_security_group(self) -> ec2.SecurityGroup:
        """Get the ECS security group."""
        return self._ecs_security_group

    @property
    def database_security_group(self) -> ec2.SecurityGroup:
        """Get the database security group."""
        return self._database_security_group

    @property
    def vpc_endpoint_security_group(self) -> ec2.SecurityGroup:
        """Get the VPC endpoint security group."""
        return self._vpc_endpoint_security_group
