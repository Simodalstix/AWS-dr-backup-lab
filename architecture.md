# Tier-2 Backup & DR Lab Architecture

## Overview

This document provides a detailed view of the architecture for the Tier-2 Backup & DR Lab with Multi-Region Warm Standby pattern.

## Architecture Diagram

```mermaid
graph TD
    subgraph "Primary Region (ap-southeast-2)"
        A[VPC - 2 AZs] --> A1[ALB]
        A --> A2[ECS Fargate Service<br/>2 tasks]
        A --> A3[RDS PostgreSQL<br/>Primary Instance]
        A --> A4[S3 Bucket<br/>app-data (versioned)]
        A --> A5[S3 Bucket<br/>logs]
        A --> A6[KMS Key<br/>Multi-Region]
        A --> A7[CloudWatch<br/>Dashboard & Alarms]

        A1 --> A2
        A2 --> A3
        A2 --> A4
        A2 --> A5
        A3 --> A6
        A4 --> A6
        A5 --> A6
        A7 --> A1
        A7 --> A2
        A7 --> A3
        A7 --> A4
    end

    subgraph "Secondary Region (us-west-2)"
        B[VPC - Mirrored Subnets] --> B1[ALB<br/>Standby]
        B --> B2[ECS Fargate Service<br/>1 task (warm standby)]
        B --> B3[RDS PostgreSQL<br/>Read Replica]
        B --> B4[S3 Bucket<br/>app-data (replicated)]
        B --> B5[KMS Key<br/>Multi-Region]
        B --> B6[Step Functions<br/>Failover Orchestration]

        B1 --> B2
        B3 --> B5
        B4 --> B5
        B6 --> B2
        B6 --> B3
        B6 --> B1
    end

    subgraph "Global Services"
        G1[Route 53<br/>Failover Routing] --> A1
        G1 --> B1
        G2[S3 Replication<br/>Cross-Region] --> A4
        G2 --> B4
        G3[RDS Replication<br/>Cross-Region] --> A3
        G3 --> B3
    end

    subgraph "Monitoring & Alerting"
        M1[CloudWatch Alarms] --> A7
        M2[SNS Notifications] --> M1
    end

    Client[External Client] --> G1
```

## Component Details

### Primary Region (ap-southeast-2)

#### Network

- VPC with 2 Availability Zones for high availability
- Public and private subnets in each AZ
- Internet Gateway for public subnet access
- NAT Gateways in each AZ for private subnet outbound access

#### Application Tier

- Application Load Balancer (ALB) distributing traffic
- ECS Fargate service running 2 tasks for redundancy
- Health check endpoint at `/healthz`
- Container images stored in ECR

#### Data Tier

- RDS PostgreSQL primary instance
- Automated backups enabled with 7-day retention
- S3 bucket for application data with versioning
- S3 bucket for logs with lifecycle policies
- Multi-Region KMS keys for encryption

#### Observability

- CloudWatch dashboard with key metrics
- Alarms for:
  - ALB 5xx errors and latency
  - ECS task count mismatches
  - RDS CPU utilization and replication lag
  - S3 replication status

### Secondary Region (us-west-2)

#### Network

- VPC with mirrored subnet configuration
- Public and private subnets
- Internet Gateway for public access

#### Warm Standby

- ECS Fargate service with minimum 1 task
- Standby ALB for failover traffic
- Pre-configured but scaled-down resources

#### Data Replication

- RDS read replica of primary database
- S3 Cross-Region Replication for app-data bucket
- Multi-Region KMS keys synchronized with primary

#### Orchestration

- Step Functions state machine for failover
- Lambda functions for specific tasks
- SNS topic for notifications

### Global Services

#### DNS & Routing

- Route 53 failover routing policy
- Health checks on primary ALB `/healthz` endpoint
- Automatic failover to secondary region

#### Data Replication

- S3 Cross-Region Replication (CRR)
- RDS Cross-Region Read Replica
- KMS Multi-Region key synchronization

## Failover Process

### Planned Failover

1. Route 53 health check detects primary failure
2. Step Functions workflow initiated
3. RDS read replica promoted to primary
4. ECS service in secondary scaled up
5. Route 53 record updated to point to secondary
6. Post-failover health checks executed
7. SNS notification sent

### Unplanned Failover

1. Route 53 health check fails
2. Automatic routing to secondary region
3. Manual intervention required for database promotion
4. ECS service scaled up in secondary
5. Post-failover validation performed
6. SNS notification sent

## Security Considerations

### Network Security

- Security groups with least-privilege access
- VPC flow logs for monitoring
- Private subnets for database resources

### Data Security

- Encryption at rest using KMS Multi-Region keys
- Encryption in transit using TLS
- S3 bucket policies restricting access
- RDS security groups limiting database access

### Identity & Access

- IAM roles for ECS task execution
- IAM policies with minimal required permissions
- KMS key policies allowing cross-region replication
- S3 replication roles with scoped permissions

## Monitoring & Alerting

### CloudWatch Metrics

- ALB request count, latency, and error rates
- ECS CPU and memory utilization
- RDS CPU, connections, and replication lag
- S3 replication bytes and object count

### Alarms

- Primary health check failure
- RDS replica lag exceeding threshold
- ECS service task count mismatch
- S3 replication failures
- High error rates on ALB

### Notifications

- SNS topic for alarm notifications
- Email subscriptions for critical alerts
- Integration with external monitoring systems via webhooks

## Cost Optimization

### Resource Sizing

- Right-sized EC2 instances for ECS tasks
- Appropriate RDS instance class for workload
- S3 lifecycle policies for cost-effective storage

### Standby Resources

- Minimal ECS tasks in standby (1 task)
- Read replica instead of full primary instance
- S3 replication only for critical data

### Monitoring

- Alarms only for critical metrics
- Dashboard with essential metrics only
- Log retention policies to control costs
