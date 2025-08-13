# CDK Constructs Overview

## Reusable Constructs for DR Lab Implementation

This document details the reusable CDK constructs that will be implemented for the Tier-2 Backup & DR Lab.

## 1. KMS Multi-Region Key Construct

### Purpose

Create and manage multi-region KMS keys for encryption across regions.

### Features

- Primary key in main region
- Replica keys in secondary regions
- Proper key policies for cross-region access
- Alias management

### Properties

- `alias`: Key alias
- `description`: Key description
- `enableKeyRotation`: Enable automatic key rotation
- `regions`: List of regions for replica keys

### Methods

- `get_key(region)`: Get key for specific region
- `grant_encrypt_decrypt(grantee)`: Grant encrypt/decrypt permissions

## 2. ECS Service with ALB Construct

### Purpose

Create an ECS service with an associated Application Load Balancer.

### Features

- ECS Fargate service
- Application Load Balancer
- Security groups
- Health checks
- Target group configuration

### Properties

- `vpc`: VPC to deploy into
- `cluster`: ECS cluster
- `image`: Container image
- `port`: Container port
- `healthCheckPath`: Health check endpoint
- `taskCount`: Number of tasks
- `minTaskCount`: Minimum tasks
- `maxTaskCount`: Maximum tasks
- `cpu`: CPU units
- `memory`: Memory in MiB

### Methods

- `get_load_balancer()`: Get the ALB
- `get_service()`: Get the ECS service
- `scale_tasks(count)`: Scale the service

## 3. RDS with Replica Construct

### Purpose

Create RDS primary instance with cross-region read replica for standard PostgreSQL.

### Features

- Primary RDS instance
- Cross-region read replica
- Automated backups
- Security groups
- Parameter groups

### Properties

- `vpc`: VPC to deploy into
- `engine`: Database engine
- `version`: Engine version
- `instanceClass`: Instance class
- `allocatedStorage`: Storage in GB
- `backupRetention`: Backup retention days
- `replicaRegion`: Region for read replica
- `replicaInstanceClass`: Replica instance class

### Methods

- `get_primary()`: Get primary instance
- `get_replica()`: Get replica instance
- `promote_replica()`: Promote replica to primary
- `restore_from_snapshot()`: Restore from latest snapshot

## 4. Aurora Global Database Construct

### Purpose

Create Aurora Global Database cluster for low RPO/RTO (optional implementation).

### Features

- Primary Aurora cluster
- Secondary Aurora cluster in different region
- Global database configuration
- Automatic failover capabilities

### Properties

- `primaryRegion`: Primary region
- `secondaryRegion`: Secondary region
- `engine`: Aurora engine
- `engineVersion`: Engine version
- `instanceClass`: Instance class
- `instances`: Number of instances

### Methods

- `get_primary_cluster()`: Get primary cluster
- `get_secondary_cluster()`: Get secondary cluster
- `switchover()`: Switchover to secondary
- `failover()`: Failover to secondary

## 5. S3 Replication Pair Construct

### Purpose

Create S3 buckets with cross-region replication configuration.

### Features

- Source bucket with versioning
- Destination bucket with versioning
- Replication configuration
- Lifecycle policies
- Encryption with KMS

### Properties

- `sourceRegion`: Source region
- `destinationRegion`: Destination region
- `bucketNamePrefix`: Prefix for bucket names
- `versioned`: Enable versioning
- `replicateDeletes`: Replicate delete markers
- `lifecycleRules`: Lifecycle configuration
- `encryptionKey`: KMS key for encryption

### Methods

- `get_source_bucket()`: Get source bucket
- `get_destination_bucket()`: Get destination bucket
- `get_replication_role()`: Get replication role

## 6. DynamoDB Global Table Construct

### Purpose

Create DynamoDB global tables for multi-region data replication (optional).

### Features

- Primary table
- Replica tables in other regions
- PITR configuration
- Auto-scaling

### Properties

- `tableName`: Table name
- `regions`: List of regions
- `billingMode`: Billing mode
- `pitrEnabled`: Enable point-in-time recovery

### Methods

- `get_table(region)`: Get table for specific region
- `add_replica(region)`: Add replica to region

## 7. Dashboards and Alarms Construct

### Purpose

Create CloudWatch dashboards and alarms for monitoring the DR environment.

### Features

- Predefined dashboards
- Alarms for critical metrics
- SNS topic for notifications

### Properties

- `dashboardName`: Dashboard name
- `alarmTopic`: SNS topic for alarms
- `resources`: Resources to monitor
- `alarmEmail`: Email for notifications

### Methods

- `get_dashboard()`: Get the dashboard
- `get_alarm_topic()`: Get the SNS topic
- `add_alarm(alarm)`: Add custom alarm

## 8. Step Functions Failover Construct

### Purpose

Create Step Functions state machine for orchestrating failover procedures.

### Features

- State machine definition
- Lambda functions for tasks
- IAM roles and policies
- SNS notifications

### Properties

- `stateMachineName`: Name of the state machine
- `dbConstruct`: Database construct reference
- `ecsConstruct`: ECS construct reference
- `routingConstruct`: Routing construct reference
- `notificationTopic`: SNS topic for notifications

### Methods

- `get_state_machine()`: Get the state machine
- `start_execution(input)`: Start execution with input
- `add_task(task)`: Add custom task to workflow

## Implementation Plan

### Phase 1: Core Constructs

1. KMS Multi-Region Key Construct
2. ECS Service with ALB Construct
3. RDS with Replica Construct
4. S3 Replication Pair Construct

### Phase 2: Monitoring and Orchestration

1. Dashboards and Alarms Construct
2. Step Functions Failover Construct

### Phase 3: Advanced Constructs

1. Aurora Global Database Construct
2. DynamoDB Global Table Construct

## Dependencies

- AWS CDK v2
- Python 3.8+
- boto3
- Constructs will be implemented in `infra/constructs/` directory
- Each construct will have its own file
- Unit tests will be implemented in `infra/tests/`

## Testing Strategy

### Unit Tests

- Test construct instantiation
- Test property validation
- Test method outputs
- Test error conditions

### Integration Tests

- Test construct wiring
- Test cross-construct interactions
- Test deployment scenarios

### Assertion Tests

- Test critical resource creation
- Test security configurations
- Test networking configurations
- Test IAM policies
