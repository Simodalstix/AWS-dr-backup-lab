"""
Deployment Automation Construct
Lambda functions for automated CloudFormation stack deployment.
"""

from typing import Dict
from aws_cdk import (
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_s3 as s3,
    Duration,
    Stack,
    CfnOutput,
)
from constructs import Construct


class DeploymentAutomation(Construct):
    """
    A construct that creates Lambda functions for automated stack deployment.

    This construct provides:
    - Lambda functions for CloudFormation stack operations
    - IAM roles with appropriate permissions
    - Error handling and status reporting
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        template_bucket: s3.IBucket,
        primary_region: str,
        secondary_region: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self._template_bucket = template_bucket
        self._primary_region = primary_region
        self._secondary_region = secondary_region

        # Create IAM role
        self._create_deployment_role()

        # Create Lambda functions
        self._create_deployment_functions()

        # Create outputs
        self._create_outputs()

    def _create_deployment_role(self) -> None:
        """Create IAM role for deployment automation."""

        self._deployment_role = iam.Role(
            self,
            "DeploymentRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # CloudFormation permissions
        self._deployment_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudformation:CreateStack",
                    "cloudformation:UpdateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:GetTemplate",
                ],
                resources=["*"],
            )
        )

        # S3 permissions for template access
        self._template_bucket.grant_read(self._deployment_role)

        # SSM permissions for parameter access
        self._deployment_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                ],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/dr-lab/*"
                ],
            )
        )

        # EC2 and ECS permissions for infrastructure deployment
        self._deployment_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:*",
                    "ecs:*",
                    "elasticloadbalancing:*",
                    "iam:PassRole",
                    "logs:*",
                ],
                resources=["*"],
            )
        )

    def _create_deployment_functions(self) -> None:
        """Create Lambda functions for deployment automation."""

        # Stack deployment function
        self._stack_deployment_function = _lambda.Function(
            self,
            "StackDeploymentFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    cfn_client = boto3.client('cloudformation')
    s3_client = boto3.client('s3')
    ssm_client = boto3.client('ssm')
    
    try:
        # Get deployment parameters
        stack_name = event['stack_name']
        template_url = event['template_url']
        parameters = event.get('parameters', [])
        
        logger.info(f"Deploying stack: {stack_name}")
        logger.info(f"Template URL: {template_url}")
        
        # Check if stack exists
        try:
            cfn_client.describe_stacks(StackName=stack_name)
            stack_exists = True
        except ClientError:
            stack_exists = False
        
        # Create or update stack
        if stack_exists:
            response = cfn_client.update_stack(
                StackName=stack_name,
                TemplateURL=template_url,
                Parameters=parameters,
                Capabilities=['CAPABILITY_IAM']
            )
            operation = 'update'
        else:
            response = cfn_client.create_stack(
                StackName=stack_name,
                TemplateURL=template_url,
                Parameters=parameters,
                Capabilities=['CAPABILITY_IAM'],
                Tags=[
                    {'Key': 'Project', 'Value': 'DR-Lab'},
                    {'Key': 'Environment', 'Value': 'Recovery'},
                    {'Key': 'CreatedBy', 'Value': 'DeploymentAutomation'}
                ]
            )
            operation = 'create'
        
        stack_id = response['StackId']
        
        logger.info(f"Stack {operation} initiated: {stack_name} ({stack_id})")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'operation': operation,
                'stack_name': stack_name,
                'stack_id': stack_id,
                'status': 'IN_PROGRESS'
            })
        }
        
    except Exception as e:
        logger.error(f"Stack deployment failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
"""
            ),
            role=self._deployment_role,
            timeout=Duration.seconds(300),
            environment={
                "TEMPLATE_BUCKET": self._template_bucket.bucket_name,
                "PRIMARY_REGION": self._primary_region,
                "SECONDARY_REGION": self._secondary_region,
            },
        )

        # Stack status checker function
        self._stack_status_function = _lambda.Function(
            self,
            "StackStatusFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    cfn_client = boto3.client('cloudformation')
    
    try:
        stack_name = event['stack_name']
        
        # Get stack status
        response = cfn_client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        
        stack_status = stack['StackStatus']
        
        # Get stack outputs if available
        outputs = {}
        for output in stack.get('Outputs', []):
            outputs[output['OutputKey']] = output['OutputValue']
        
        # Determine if operation is complete
        complete_statuses = [
            'CREATE_COMPLETE',
            'UPDATE_COMPLETE',
            'CREATE_FAILED',
            'UPDATE_FAILED',
            'ROLLBACK_COMPLETE',
            'UPDATE_ROLLBACK_COMPLETE'
        ]
        
        is_complete = stack_status in complete_statuses
        is_success = stack_status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']
        
        logger.info(f"Stack {stack_name} status: {stack_status}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'stack_name': stack_name,
                'stack_status': stack_status,
                'is_complete': is_complete,
                'is_success': is_success,
                'outputs': outputs
            })
        }
        
    except Exception as e:
        logger.error(f"Stack status check failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
"""
            ),
            role=self._deployment_role,
            timeout=Duration.seconds(60),
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "StackDeploymentFunctionArn",
            value=self._stack_deployment_function.function_arn,
            description="ARN of the stack deployment function",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-DeploymentArn",
        )

        CfnOutput(
            self,
            "StackStatusFunctionArn",
            value=self._stack_status_function.function_arn,
            description="ARN of the stack status function",
            export_name=f"{Stack.of(self).stack_name}-{self.node.id}-StatusArn",
        )

    @property
    def deployment_role(self) -> iam.Role:
        """Get the deployment IAM role."""
        return self._deployment_role

    @property
    def stack_deployment_function(self) -> _lambda.Function:
        """Get the stack deployment function."""
        return self._stack_deployment_function

    @property
    def stack_status_function(self) -> _lambda.Function:
        """Get the stack status function."""
        return self._stack_status_function
