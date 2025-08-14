"""
Routing and DR Orchestration Stack
Implements global routing and disaster recovery orchestration.
"""

from typing import Dict, Optional
from aws_cdk import (
    Stack,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_rds as rds,
    aws_ecs as ecs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_logs as logs,
    Duration,
    CfnOutput,
    Tags,
)
from constructs import Construct


class RoutingAndDROrchestrationStack(Stack):
    """
    Stack that implements global routing and DR orchestration.

    This stack creates:
    - Route 53 failover records
    - Route 53 health checks
    - Step Functions state machine for failover orchestration
    - Lambda functions for orchestration tasks
    - SNS topic for notifications
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        primary_alb: elbv2.ApplicationLoadBalancer,
        secondary_alb: elbv2.ApplicationLoadBalancer,
        primary_database: rds.DatabaseInstance,
        secondary_database: rds.DatabaseInstance,
        primary_ecs_service: ecs.FargateService,
        secondary_ecs_service: ecs.FargateService,
        config: Dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._primary_alb = primary_alb
        self._secondary_alb = secondary_alb
        self._primary_database = primary_database
        self._secondary_database = secondary_database
        self._primary_ecs_service = primary_ecs_service
        self._secondary_ecs_service = secondary_ecs_service
        self._config = config

        # Create SNS topic for notifications
        self._create_notification_topic()

        # Create Route 53 resources
        self._create_route53_resources()

        # Create Lambda functions for orchestration
        self._create_lambda_functions()

        # Create Step Functions state machine
        self._create_state_machine()

        # Create outputs
        self._create_outputs()

        # Add tags
        self._add_tags()

    def _create_notification_topic(self) -> None:
        """Create SNS topic for DR notifications."""

        self._notification_topic = sns.Topic(
            self,
            "NotificationTopic",
            display_name="DR Lab Notifications",
            topic_name="dr-lab-notifications",
        )

        # Add email subscription if configured
        alarm_email = self._config.get("alarm_email")
        if alarm_email:
            self._notification_topic.add_subscription(
                subs.EmailSubscription(alarm_email)
            )

        # Add webhook subscription if configured
        webhook_url = self._config.get("webhook_url")
        if webhook_url:
            self._notification_topic.add_subscription(subs.UrlSubscription(webhook_url))

    def _create_route53_resources(self) -> None:
        """Create Route 53 failover records and health checks."""

        # Get hosted zone
        hosted_zone_id = self._config.get("hosted_zone_id")
        domain_name = self._config.get("domain_name", "app.example.com")

        # If hosted zone ID is provided, import it
        if hosted_zone_id:
            self._hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
                self, "HostedZone", hosted_zone_id=hosted_zone_id, zone_name=domain_name
            )
        else:
            # Create a placeholder hosted zone for demonstration
            # In a real implementation, you would either import an existing zone
            # or create a new one if you have domain registration rights
            self._hosted_zone = route53.HostedZone(
                self, "HostedZone", zone_name=domain_name
            )

        # Create health check for primary ALB
        self._primary_health_check = route53.HealthCheck(
            self,
            "PrimaryHealthCheck",
            health_check_config=route53.HealthCheckConfig(
                type=route53.HealthCheckType.HTTP,
                resource_path=self._config.get("health_check_path", "/healthz"),
                fully_qualified_domain_name=self._primary_alb.load_balancer_dns_name,
                port=80,
                request_interval=route53.HealthCheckInterval.SECONDS_30,
                failure_threshold=3,
                measure_latency=True,
            ),
        )

        # Create primary failover record
        self._failover_record = route53.ARecord(
            self,
            "FailoverRecord",
            zone=self._hosted_zone,
            record_name=domain_name,
            target=route53.RecordTarget.from_alias(
                targets.LoadBalancerTarget(self._primary_alb)
            ),
            set_identifier="primary",
            failover=route53.Failover.PRIMARY,
            health_check=self._primary_health_check,
        )

        # Create secondary failover record
        self._secondary_failover_record = route53.ARecord(
            self,
            "SecondaryFailoverRecord",
            zone=self._hosted_zone,
            record_name=domain_name,
            target=route53.RecordTarget.from_alias(
                targets.LoadBalancerTarget(self._secondary_alb)
            ),
            set_identifier="secondary",
            failover=route53.Failover.SECONDARY,
        )

    def _create_lambda_functions(self) -> None:
        """Create Lambda functions for DR orchestration tasks."""

        # Create Lambda execution role
        self._lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Add permissions for Lambda functions
        self._lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "rds:PromoteReadReplica",
                    "rds:ModifyDBInstance",
                    "rds:DescribeDBInstances",
                ],
                resources=["*"],  # In production, scope this to specific resources
            )
        )

        self._lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecs:UpdateService", "ecs:DescribeServices"],
                resources=["*"],  # In production, scope this to specific resources
            )
        )

        self._lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["route53:ChangeResourceRecordSets", "route53:GetChange"],
                resources=["*"],  # In production, scope this to specific resources
            )
        )

        self._lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:PutSecretValue",
                    "secretsmanager:UpdateSecret",
                ],
                resources=["*"],  # In production, scope this to specific resources
            )
        )

        # Create Lambda function to check primary health
        self._check_primary_health_function = _lambda.Function(
            self,
            "CheckPrimaryHealth",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3

def handler(event, context):
    # In a real implementation, this would check the actual health
    # For demonstration, we'll return a mock response
    return {
        "statusCode": 200,
        "body": json.dumps({
            "healthy": True,
            "message": "Primary is healthy"
        })
    }
"""
            ),
            role=self._lambda_role,
            timeout=Duration.seconds(30),
            environment={"PRIMARY_ALB_DNS": self._primary_alb.load_balancer_dns_name},
        )

        # Create Lambda function to promote database replica
        self._promote_replica_function = _lambda.Function(
            self,
            "PromoteReplica",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3

def handler(event, context):
    rds = boto3.client('rds')
    
    # In a real implementation, this would promote the actual replica
    # For demonstration, we'll return a mock response
    try:
        # rds.promote_read_replica(
        #     DBInstanceIdentifier='dr-lab-secondary-replica'
        # )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Replica promoted successfully"
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }
"""
            ),
            role=self._lambda_role,
            timeout=Duration.seconds(300),  # Longer timeout for database operations
            environment={
                "SECONDARY_DB_IDENTIFIER": self._secondary_database.instance_identifier
            },
        )

        # Create Lambda function to scale ECS service
        self._scale_ecs_function = _lambda.Function(
            self,
            "ScaleECS",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3

def handler(event, context):
    ecs = boto3.client('ecs')
    
    # In a real implementation, this would scale the actual service
    # For demonstration, we'll return a mock response
    try:
        desired_count = event.get('desiredCount', 2)
        
        # ecs.update_service(
        #     cluster='dr-lab-secondary-cluster',
        #     service='dr-lab-secondary-service',
        #     desiredCount=desired_count
        # )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"ECS service scaled to {desired_count} tasks"
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }
"""
            ),
            role=self._lambda_role,
            timeout=Duration.seconds(60),
            environment={
                "SECONDARY_CLUSTER_NAME": self._secondary_ecs_service.cluster.cluster_name,
                "SECONDARY_SERVICE_NAME": self._secondary_ecs_service.service_name,
            },
        )

        # Create Lambda function to update Route 53
        self._update_route53_function = _lambda.Function(
            self,
            "UpdateRoute53",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3

def handler(event, context):
    route53 = boto3.client('route53')
    
    # In a real implementation, this would update the actual records
    # For demonstration, we'll return a mock response
    try:
        # route53.change_resource_record_sets(
        #     HostedZoneId='ZONE_ID',
        #     ChangeBatch={
        #         'Changes': [{
        #             'Action': 'UPSERT',
        #             'ResourceRecordSet': {
        #                 'Name': 'app.example.com',
        #                 'Type': 'A',
        #                 'AliasTarget': {
        #                     'DNSName': 'secondary-alb-dns',
        #                     'HostedZoneId': 'SECONDARY_ALB_ZONE_ID',
        #                     'EvaluateTargetHealth': True
        #                 }
        #             }
        #         }]
        #     }
        # )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Route 53 record updated"
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }
"""
            ),
            role=self._lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "HOSTED_ZONE_ID": self._config.get("hosted_zone_id", ""),
                "DOMAIN_NAME": self._config.get("domain_name", "app.example.com"),
            },
        )

        # Create Lambda function for post-checks
        self._post_checks_function = _lambda.Function(
            self,
            "PostChecks",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3

def handler(event, context):
    # In a real implementation, this would perform actual post-failover checks
    # For demonstration, we'll return a mock response
    return {
        "statusCode": 200,
        "body": json.dumps({
            "healthy": True,
            "message": "Post-failover checks passed"
        })
    }
"""
            ),
            role=self._lambda_role,
            timeout=Duration.seconds(60),
        )

        # Create Lambda function to send notifications
        self._notify_function = _lambda.Function(
            self,
            "Notify",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                f"""
import json
import boto3

def handler(event, context):
    sns = boto3.client('sns')
    
    # In a real implementation, this would send actual notifications
    # For demonstration, we'll return a mock response
    try:
        message = event.get('message', 'DR event occurred')
        subject = event.get('subject', 'DR Notification')
        
        # sns.publish(
        #     TopicArn='{self._notification_topic.topic_arn}',
        #     Message=message,
        #     Subject=subject
        # )
        return {{
            "statusCode": 200,
            "body": json.dumps({{
                "message": "Notification sent"
            }})
        }}
    except Exception as e:
        return {{
            "statusCode": 500,
            "body": json.dumps({{
                "error": str(e)
            }})
        }}
"""
            ),
            role=self._lambda_role,
            timeout=Duration.seconds(30),
            environment={"NOTIFICATION_TOPIC_ARN": self._notification_topic.topic_arn},
        )

    def _create_state_machine(self) -> None:
        """Create Step Functions state machine for DR orchestration."""

        # Define the state machine
        # Check primary health
        check_primary_health = tasks.LambdaInvoke(
            self,
            "CheckPrimaryHealthTask",
            lambda_function=self._check_primary_health_function,
            output_path="$.Payload",
        )

        # Decide if we need to failover
        decide_failover = sfn.Choice(self, "DecideFailover")

        # Promote replica
        promote_replica = tasks.LambdaInvoke(
            self,
            "PromoteReplicaTask",
            lambda_function=self._promote_replica_function,
            output_path="$.Payload",
        )

        # Scale ECS service
        scale_ecs = tasks.LambdaInvoke(
            self,
            "ScaleECSTask",
            lambda_function=self._scale_ecs_function,
            input_path="$.scaleInput",
            output_path="$.Payload",
        )

        # Update Route 53
        update_route53 = tasks.LambdaInvoke(
            self,
            "UpdateRoute53Task",
            lambda_function=self._update_route53_function,
            output_path="$.Payload",
        )

        # Post checks
        post_checks = tasks.LambdaInvoke(
            self,
            "PostChecksTask",
            lambda_function=self._post_checks_function,
            output_path="$.Payload",
        )

        # Notify
        notify = tasks.LambdaInvoke(
            self,
            "NotifyTask",
            lambda_function=self._notify_function,
            input_path="$.notifyInput",
            output_path="$.Payload",
        )

        # Wait states
        wait_for_promotion = sfn.Wait(
            self, "WaitForPromotion", time=sfn.WaitTime.duration(Duration.seconds(30))
        )

        wait_for_scaling = sfn.Wait(
            self, "WaitForScaling", time=sfn.WaitTime.duration(Duration.seconds(30))
        )

        # Build the state machine
        definition = check_primary_health.next(
            decide_failover.when(
                sfn.Condition.boolean_equals("$.healthy", False),
                promote_replica.next(
                    wait_for_promotion.next(
                        scale_ecs.next(
                            wait_for_scaling.next(
                                update_route53.next(post_checks.next(notify))
                            )
                        )
                    )
                ),
            ).otherwise(sfn.Pass(self, "PrimaryHealthy"))
        )

        # Create the state machine
        self._state_machine = sfn.StateMachine(
            self,
            "DRStateMachine",
            definition=definition,
            state_machine_name="dr-lab-failover",
            timeout=Duration.minutes(60),
            logs=sfn.LogOptions(
                destination=logs.LogGroup(
                    self,
                    "StateMachineLogGroup",
                    log_group_name="/aws/states/dr-lab-failover",
                    retention=logs.RetentionDays.TWO_WEEKS,
                ),
                level=sfn.LogLevel.ALL,
            ),
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        # Route 53 outputs
        CfnOutput(
            self,
            "HostedZoneId",
            value=self._hosted_zone.hosted_zone_id,
            description="ID of the Route 53 hosted zone",
            export_name=f"{self.stack_name}-HostedZoneId",
        )

        CfnOutput(
            self,
            "PrimaryHealthCheckId",
            value=self._primary_health_check.health_check_id,
            description="ID of the primary health check",
            export_name=f"{self.stack_name}-PrimaryHealthCheckId",
        )

        CfnOutput(
            self,
            "FailoverRecordName",
            value=self._failover_record.domain_name,
            description="Name of the failover record",
            export_name=f"{self.stack_name}-FailoverRecordName",
        )

        # SNS outputs
        CfnOutput(
            self,
            "NotificationTopicArn",
            value=self._notification_topic.topic_arn,
            description="ARN of the notification topic",
            export_name=f"{self.stack_name}-NotificationTopicArn",
        )

        # Step Functions outputs
        CfnOutput(
            self,
            "StateMachineArn",
            value=self._state_machine.state_machine_arn,
            description="ARN of the DR state machine",
            export_name=f"{self.stack_name}-StateMachineArn",
        )

        # Application endpoint
        CfnOutput(
            self,
            "ApplicationEndpoint",
            value=f"http://{self._config.get('domain_name', 'app.example.com')}",
            description="Application endpoint with failover routing",
            export_name=f"{self.stack_name}-ApplicationEndpoint",
        )

    def _add_tags(self) -> None:
        """Add tags to all resources in this stack."""

        Tags.of(self).add("Component", "RoutingAndOrchestration")
        Tags.of(self).add("Environment", "Production")

    @property
    def notification_topic(self) -> sns.Topic:
        """Get the notification SNS topic."""
        return self._notification_topic

    @property
    def state_machine(self) -> sfn.StateMachine:
        """Get the Step Functions state machine."""
        return self._state_machine

    @property
    def hosted_zone(self) -> route53.IHostedZone:
        """Get the Route 53 hosted zone."""
        return self._hosted_zone

    @property
    def primary_health_check(self) -> route53.HealthCheck:
        """Get the primary health check."""
        return self._primary_health_check

    def start_failover_execution(self, input_data: Dict) -> None:
        """Start a failover execution (for testing purposes)."""
        # This would typically be done through AWS APIs in a real scenario
        # For CDK, we can't actually start executions, but we can document the method
        pass
