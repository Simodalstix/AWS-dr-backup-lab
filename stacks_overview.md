# CDK Stack Modules Overview

## Stack Organization for DR Lab Implementation

This document details the CDK stack modules that will be implemented for the Tier-2 Backup & DR Lab.

## Stack Architecture

The application will be organized into multiple stacks to separate concerns and enable independent deployment:

```
Primary Region Stacks:
├── PrimaryNetworkStack
├── PrimaryAppStack
└── PrimaryDataStack

Secondary Region Stacks:
├── SecondaryNetworkStack
├── SecondaryAppStack
└── SecondaryDataStack

Global Stacks:
├── RoutingAndDROrchestrationStack
└── ObservabilityStack
```

## Primary Region Stacks

### 1. PrimaryNetworkStack

#### Purpose

Create the foundational network infrastructure in the primary region.

#### Resources

- VPC with 2 Availability Zones
- Public and private subnets in each AZ
- Internet Gateway
- NAT Gateways in each AZ
- Route tables and associations
- Security groups for different tiers

#### Outputs

- VPC reference
- Public subnet IDs
- Private subnet IDs
- Security group IDs

#### Parameters

- `cidr`: VPC CIDR block
- `availabilityZones`: List of AZs to use
- `natGateways`: Number of NAT gateways

### 2. PrimaryAppStack

#### Purpose

Deploy the application infrastructure in the primary region.

#### Resources

- ECS cluster
- ECS Fargate service with 2 tasks
- Application Load Balancer
- Target groups
- Security groups
- IAM roles for ECS

#### Outputs

- ALB DNS name
- ECS service reference
- Load balancer ARN

#### Parameters

- `vpc`: VPC reference from PrimaryNetworkStack
- `image`: Container image to deploy
- `taskCount`: Number of tasks to run
- `cpu`: CPU units for tasks
- `memory`: Memory for tasks

### 3. PrimaryDataStack

#### Purpose

Deploy the data infrastructure in the primary region.

#### Resources

- RDS primary instance (PostgreSQL)
- S3 bucket for application data
- S3 bucket for logs
- KMS key for encryption
- Security groups
- IAM roles and policies

#### Outputs

- RDS endpoint
- S3 bucket names
- KMS key ARN

#### Parameters

- `vpc`: VPC reference from PrimaryNetworkStack
- `dbName`: Database name
- `dbInstanceClass`: RDS instance class
- `allocatedStorage`: Storage allocation
- `backupRetention`: Backup retention period

## Secondary Region Stacks

### 1. SecondaryNetworkStack

#### Purpose

Create the network infrastructure in the secondary region, mirroring the primary.

#### Resources

- VPC with mirrored subnet configuration
- Public and private subnets
- Internet Gateway
- Route tables and associations
- Security groups

#### Outputs

- VPC reference
- Public subnet IDs
- Private subnet IDs
- Security group IDs

#### Parameters

- `cidr`: VPC CIDR block
- `availabilityZones`: List of AZs to use
- `mirrorSubnets`: Subnet configuration to mirror

### 2. SecondaryAppStack

#### Purpose

Deploy the warm standby application infrastructure in the secondary region.

#### Resources

- ECS cluster
- ECS Fargate service with 1 task (warm standby)
- Application Load Balancer (standby)
- Target groups
- Security groups
- IAM roles for ECS

#### Outputs

- Standby ALB DNS name
- ECS service reference

#### Parameters

- `vpc`: VPC reference from SecondaryNetworkStack
- `image`: Container image to deploy
- `taskCount`: Number of tasks to run (default: 1)
- `cpu`: CPU units for tasks
- `memory`: Memory for tasks

### 3. SecondaryDataStack

#### Purpose

Deploy the data replication infrastructure in the secondary region.

#### Resources

- RDS read replica
- S3 bucket for replicated application data
- KMS key for encryption
- S3 replication configuration
- Security groups
- IAM roles and policies

#### Outputs

- RDS replica endpoint
- S3 bucket names
- KMS key ARN

#### Parameters

- `vpc`: VPC reference from SecondaryNetworkStack
- `primaryDbEndpoint`: Primary database endpoint
- `primaryDbSecret`: Primary database secret
- `primaryS3Bucket`: Primary S3 bucket for replication

## Global Stacks

### 1. RoutingAndDROrchestrationStack

#### Purpose

Implement global routing and disaster recovery orchestration.

#### Resources

- Route 53 hosted zone (if creating)
- Route 53 failover records
- Route 53 health checks
- Step Functions state machine
- Lambda functions for orchestration tasks
- SNS topic for notifications
- IAM roles and policies

#### Outputs

- Route 53 failover record
- State machine ARN
- SNS topic ARN

#### Parameters

- `primaryAlbDns`: Primary ALB DNS name
- `secondaryAlbDns`: Secondary ALB DNS name
- `hostedZoneId`: Route 53 hosted zone ID
- `domainName`: Domain name for failover record

### 2. ObservabilityStack

#### Purpose

Implement monitoring and observ
