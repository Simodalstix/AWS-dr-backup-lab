"""
Observability Stack
Implements monitoring and observability for the DR environment.
"""

from typing import Dict, List
from aws_cdk import (
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecs as ecs,
    aws_rds as rds,
    aws_s3 as s3,
    Duration,
    CfnOutput,
    Tags,
)
from constructs import Construct


class ObservabilityStack(Stack):
    """
    Stack that implements monitoring and observability for the DR environment.

    This stack creates:
    - CloudWatch dashboard with key metrics
    - Alarms for critical metrics
    - SNS topics for notifications
    - Log groups and retention policies
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
        s3_buckets: List[s3.Bucket],
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
        self._s3_buckets = s3_buckets
        self._config = config

        # Create notification topic
        self._create_notification_topic()

        # Create CloudWatch dashboard
        self._create_dashboard()

        # Create alarms
        self._create_alarms()

        # Create outputs
        self._create_outputs()

        # Add tags
        self._add_tags()

    def _create_notification_topic(self) -> None:
        """Create SNS topic for monitoring notifications."""

        self._notification_topic = sns.Topic(
            self,
            "MonitoringNotificationTopic",
            display_name="DR Lab Monitoring Notifications",
            topic_name="dr-lab-monitoring-notifications",
        )

        # Add email subscription if configured
        alarm_email = self._config.get("alarm_email")
        if alarm_email:
            self._notification_topic.add_subscription(
                sns.Subscription.email(alarm_email)
            )

    def _create_dashboard(self) -> None:
        """Create CloudWatch dashboard with key metrics."""

        self._dashboard = cloudwatch.Dashboard(
            self, "DRDashboard", dashboard_name="DR-Lab-Dashboard"
        )

        # ALB Metrics - Primary Region
        primary_alb_5xx_widget = cloudwatch.GraphWidget(
            title="Primary ALB 5xx Errors",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="HTTPCode_ELB_5XX_Count",
                    dimensions_map={
                        "LoadBalancer": self._primary_alb.load_balancer_full_name
                    },
                    statistic="Sum",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0),
        )

        primary_alb_latency_widget = cloudwatch.GraphWidget(
            title="Primary ALB Latency",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="TargetResponseTime",
                    dimensions_map={
                        "LoadBalancer": self._primary_alb.load_balancer_full_name
                    },
                    statistic="p95",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0),
        )

        # ALB Metrics - Secondary Region
        secondary_alb_5xx_widget = cloudwatch.GraphWidget(
            title="Secondary ALB 5xx Errors",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="HTTPCode_ELB_5XX_Count",
                    dimensions_map={
                        "LoadBalancer": self._secondary_alb.load_balancer_full_name
                    },
                    statistic="Sum",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0),
        )

        secondary_alb_latency_widget = cloudwatch.GraphWidget(
            title="Secondary ALB Latency",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="TargetResponseTime",
                    dimensions_map={
                        "LoadBalancer": self._secondary_alb.load_balancer_full_name
                    },
                    statistic="p95",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0),
        )

        # ECS Metrics - Primary Region
        primary_ecs_cpu_widget = cloudwatch.GraphWidget(
            title="Primary ECS CPU Utilization",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="CPUUtilization",
                    dimensions_map={
                        "ClusterName": self._primary_ecs_service.cluster.cluster_name,
                        "ServiceName": self._primary_ecs_service.service_name,
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
        )

        primary_ecs_memory_widget = cloudwatch.GraphWidget(
            title="Primary ECS Memory Utilization",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="MemoryUtilization",
                    dimensions_map={
                        "ClusterName": self._primary_ecs_service.cluster.cluster_name,
                        "ServiceName": self._primary_ecs_service.service_name,
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
        )

        # ECS Metrics - Secondary Region
        secondary_ecs_cpu_widget = cloudwatch.GraphWidget(
            title="Secondary ECS CPU Utilization",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="CPUUtilization",
                    dimensions_map={
                        "ClusterName": self._secondary_ecs_service.cluster.cluster_name,
                        "ServiceName": self._secondary_ecs_service.service_name,
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
        )

        secondary_ecs_memory_widget = cloudwatch.GraphWidget(
            title="Secondary ECS Memory Utilization",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="MemoryUtilization",
                    dimensions_map={
                        "ClusterName": self._secondary_ecs_service.cluster.cluster_name,
                        "ServiceName": self._secondary_ecs_service.service_name,
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
        )

        # RDS Metrics - Primary Region
        primary_rds_cpu_widget = cloudwatch.GraphWidget(
            title="Primary RDS CPU Utilization",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/RDS",
                    metric_name="CPUUtilization",
                    dimensions_map={
                        "DBInstanceIdentifier": self._primary_database.instance_identifier
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
        )

        primary_rds_connections_widget = cloudwatch.GraphWidget(
            title="Primary RDS Connections",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/RDS",
                    metric_name="DatabaseConnections",
                    dimensions_map={
                        "DBInstanceIdentifier": self._primary_database.instance_identifier
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0),
        )

        # RDS Metrics - Secondary Region
        secondary_rds_cpu_widget = cloudwatch.GraphWidget(
            title="Secondary RDS CPU Utilization",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/RDS",
                    metric_name="CPUUtilization",
                    dimensions_map={
                        "DBInstanceIdentifier": self._secondary_database.instance_identifier
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
        )

        secondary_rds_connections_widget = cloudwatch.GraphWidget(
            title="Secondary RDS Connections",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/RDS",
                    metric_name="DatabaseConnections",
                    dimensions_map={
                        "DBInstanceIdentifier": self._secondary_database.instance_identifier
                    },
                    statistic="Average",
                    period=Duration.minutes(1),
                )
            ],
            left_y_axis=cloudwatch.YAxisProps(min=0),
        )

        # S3 Metrics
        s3_metrics_widgets = []
        for i, bucket in enumerate(
            self._s3_buckets[:4]
        ):  # Limit to 4 buckets for dashboard
            s3_widget = cloudwatch.GraphWidget(
                title=f"S3 Bucket {bucket.bucket_name} Metrics",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/S3",
                        metric_name="NumberOfObjects",
                        dimensions_map={
                            "BucketName": bucket.bucket_name,
                            "StorageType": "StandardStorage",
                        },
                        statistic="Average",
                        period=Duration.hours(1),
                    )
                ],
                left_y_axis=cloudwatch.YAxisProps(min=0),
            )
            s3_metrics_widgets.append(s3_widget)

        # Add widgets to dashboard
        self._dashboard.add_widgets(
            cloudwatch.Row(
                primary_alb_5xx_widget,
                primary_alb_latency_widget,
                secondary_alb_5xx_widget,
                secondary_alb_latency_widget,
            ),
            cloudwatch.Row(
                primary_ecs_cpu_widget,
                primary_ecs_memory_widget,
                secondary_ecs_cpu_widget,
                secondary_ecs_memory_widget,
            ),
            cloudwatch.Row(
                primary_rds_cpu_widget,
                primary_rds_connections_widget,
                secondary_rds_cpu_widget,
                secondary_rds_connections_widget,
            ),
        )

        # Add S3 widgets if there are any
        if s3_metrics_widgets:
            s3_row = cloudwatch.Row(*s3_metrics_widgets)
            self._dashboard.add_widgets(s3_row)

    def _create_alarms(self) -> None:
        """Create CloudWatch alarms for critical metrics."""

        # ALB 5xx Error Rate Alarm - Primary
        primary_alb_5xx_alarm = cloudwatch.Alarm(
            self,
            "PrimaryALB5xxAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="HTTPCode_ELB_5XX_Count",
                dimensions_map={
                    "LoadBalancer": self._primary_alb.load_balancer_full_name
                },
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=10,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Primary ALB 5xx error rate is too high",
            alarm_name="dr-lab-primary-alb-5xx-errors",
        )

        # Add action to alarm
        primary_alb_5xx_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self._notification_topic)
        )

        # ALB Latency Alarm - Primary
        primary_alb_latency_alarm = cloudwatch.Alarm(
            self,
            "PrimaryALBLatencyAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="TargetResponseTime",
                dimensions_map={
                    "LoadBalancer": self._primary_alb.load_balancer_full_name
                },
                statistic="p95",
                period=Duration.minutes(5),
            ),
            threshold=2.0,  # 2 seconds
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Primary ALB latency is too high",
            alarm_name="dr-lab-primary-alb-latency",
        )

        # Add action to alarm
        primary_alb_latency_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self._notification_topic)
        )

        # ECS Task Count Mismatch - Primary
        primary_ecs_task_alarm = cloudwatch.Alarm(
            self,
            "PrimaryECSTaskCountAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="RunningTaskCount",
                dimensions_map={
                    "ClusterName": self._primary_ecs_service.cluster.cluster_name,
                    "ServiceName": self._primary_ecs_service.service_name,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=1,  # Less than 1 task running
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            alarm_description="Primary ECS service has insufficient running tasks",
            alarm_name="dr-lab-primary-ecs-task-count",
        )

        # Add action to alarm
        primary_ecs_task_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self._notification_topic)
        )

        # RDS CPU Utilization - Primary
        primary_rds_cpu_alarm = cloudwatch.Alarm(
            self,
            "PrimaryRDS CPUAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="CPUUtilization",
                dimensions_map={
                    "DBInstanceIdentifier": self._primary_database.instance_identifier
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Primary RDS CPU utilization is too high",
            alarm_name="dr-lab-primary-rds-cpu",
        )

        # Add action to alarm
        primary_rds_cpu_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self._notification_topic)
        )

        # Health Check Failure Alarm
        health_check_alarm = cloudwatch.Alarm(
            self,
            "PrimaryHealthCheckFailureAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/Route53",
                metric_name="HealthCheckStatus",
                dimensions_map={
                    "HealthCheckId": "PRIMARY_HEALTH_CHECK_ID_PLACEHOLDER"  # This would be dynamically set
                },
                statistic="Minimum",
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            alarm_description="Primary health check is failing",
            alarm_name="dr-lab-primary-health-check-failure",
        )

        # Add action to alarm
        health_check_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self._notification_topic)
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "DashboardName",
            value=self._dashboard.dashboard_name,
            description="Name of the CloudWatch dashboard",
            export_name=f"{self.stack_name}-DashboardName",
        )

        CfnOutput(
            self,
            "NotificationTopicArn",
            value=self._notification_topic.topic_arn,
            description="ARN of the monitoring notification topic",
            export_name=f"{self.stack_name}-NotificationTopicArn",
        )

    def _add_tags(self) -> None:
        """Add tags to all resources in this stack."""

        Tags.of(self).add("Component", "Observability")
        Tags.of(self).add("Environment", "Production")

    @property
    def dashboard(self) -> cloudwatch.Dashboard:
        """Get the CloudWatch dashboard."""
        return self._dashboard

    @property
    def notification_topic(self) -> sns.Topic:
        """Get the notification SNS topic."""
        return self._notification_topic

    def add_custom_alarm(
        self,
        alarm_id: str,
        metric: cloudwatch.Metric,
        threshold: float,
        evaluation_periods: int = 2,
        comparison_operator: cloudwatch.ComparisonOperator = cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        alarm_description: str = "",
        alarm_name: str = "",
    ) -> cloudwatch.Alarm:
        """Add a custom alarm to the monitoring system."""

        alarm = cloudwatch.Alarm(
            self,
            alarm_id,
            metric=metric,
            threshold=threshold,
            evaluation_periods=evaluation_periods,
            comparison_operator=comparison_operator,
            alarm_description=alarm_description,
            alarm_name=alarm_name or f"dr-lab-{alarm_id.lower()}",
        )

        # Add action to alarm
        alarm.add_alarm_action(cloudwatch_actions.SnsAction(self._notification_topic))

        return alarm
