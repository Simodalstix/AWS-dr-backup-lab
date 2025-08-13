# Tier-2 Backup & DR Lab (Multi-Region Warm Standby) - Implementation Plan

## Project Overview

This document outlines the implementation plan for building a Tier-2 Backup & DR Lab using AWS CDK (Python v2) with a multi-region warm standby disaster recovery pattern. The solution will provide measurable RPO/RTO for a simple web/API service.

## Architecture Summary

- **Primary Region (A)**: ap-southeast-2
- **Secondary Region (B)**: us-west-2 (selected for geographic separation)
- **Database Mode**: rds-postgres (standard RDS with cross-region read replica)
- **Warm Standby Tasks**: 1 task in secondary region
- **Optional Components**: No DynamoDB global table (keep simple)

## Project Structure

```
/AWS-dr-backup-lab
  /infra
    app.py
    cdk.json
    requirements.txt
    /stacks
      primary_network.py
      primary_app.py
      primary_data.py
      secondary_network.py
      secondary_app.py
      secondary_data.py
      routing_dr_orchestration.py
      observability.py
    /constructs
      kms_multi_region_key.py
      ecs_service_alb.py
      rds_cluster_global.py
      rds_with_replica.py
      s3_replication_pair.py
      dynamodb_global_table.py
      dashboards_alarms.py
      stepfunctions_failover.py
    /tests
      test_dr_wiring.py
  /app
    Dockerfile
    app.py
  /ops
    /runbooks
      planned_failover.md
      unplanned_failover.md
      db_restore.md
      s3_undelete.md
      dynamodb_region_isolation.md
    /gamedays
      primary_outage.md
      snapshot_restore.md
      s3_ransomware.md
    /queries
      cloudwatch-insights
        alb_metrics.txt
        ecs_metrics.txt
        rds_metrics.txt
        s3_replication.txt
  README.md
```

## Implementation Steps

### 1. Project Initialization

- Create project directory structure
- Initialize CDK project with Python
- Set up requirements.txt with necessary dependencies

### 2. Core Infrastructure Components

#### Primary Region (ap-southeast-2)

- VPC with 2 AZs
- ALB + ECS Fargate service (2 tasks) serving /healthz
- RDS database (rds-postgres with cross-region read replica)
- S3 buckets: app-data (versioned, SSE-KMS) and logs (SSE-KMS, lifecycle)
- KMS keys (multi-Region keys where needed)
- CloudWatch dashboard + alarms

#### Secondary Region (us-west-2)

- VPC (mirrored subnets)
- Warm standby compute: ECS service at min=1
- RDS: cross-region read replica
- S3: replicated app-data bucket (CRR)
- KMS keys in B (paired multi-Region CMKs)

### 3. Data Protection

- RDS automated backups; cross-region snapshot copy
- S3: versioning + CRR (replication rules for prefixes), lifecycle
- No DynamoDB (as per requirement)

### 4. Routing & Health

- Route 53 failover record for app.example.com
- Health checks: Route 53 health check on /healthz via primary ALB

### 5. Failover Orchestration

- State Machine (Step Functions) with tasks:
  - Promote DB in B (promote read replica)
  - Scale ECS in B (set desired count to N)
  - Flip Route 53 to secondary
  - Post-checks (health, write test) and notify via SNS

### 6. Runbooks & GameDays

- Planned failover documentation
- Unplanned failover documentation
- DB restore from snapshot documentation
- S3 undelete/version restore documentation
- GameDay scenarios:
  - Simulate primary outage
  - Snapshot restore timing
  - S3 ransomware scenario

### 7. Documentation

- README with architecture diagram
- Target RPO/RTO documentation
- Cost estimation
- Deployment and testing commands
- Interview crib notes

### 8. Testing

- CDK tests using assertions for critical wiring and props
- Unit tests for constructs
- Integration tests for failover scenarios

## Technology Choices

### Database (rds-postgres)

- Primary: RDS PostgreSQL in ap-southeast-2
- Secondary: Cross-region read replica in us-west-2
- Failover: Promote replica or restore latest snapshot
- Note: Snapshot restore implies higher RTO/RPO

### Storage (S3)

- Enable versioning on both buckets
- CRR from A→B for app-data/ prefix
- Replicate delete markers: false (safer for "undelete" demos)
- SSE-KMS encryption with destination key configuration
- Lifecycle: IA at 30d, Glacier DA at 90d

### Routing (Route 53)

- Failover record:
  - Primary: alias to ALB A + health check on /healthz
  - Secondary: alias to ALB B (no health check required)

### Observability

- Dashboard: ALB 4xx/5xx & p95, ECS CPU/Mem, task count per region
- RDS CPU/Connections/ReplicaLag
- S3 replication bytes and backlog
- Alarms → SNS (email/webhook)

### Orchestration (Step Functions)

States:

1. CheckPrimaryHealth (Lambda)
2. DecideAuroraOrStandard (Choice by context)
3. PromoteReplica or RestoreFromLatestSnapshot
4. UpdateSecrets & RotateAppConfig (set new DB endpoint)
5. ScaleSecondaryECS (set desired count → wait for healthy)
6. FlipRoute53 (if not failover record)
7. PostChecks (run /dbcheck)
8. Notify (SNS)

## Context Configuration (cdk.json)

- dbMode = rds-postgres
- warmStandbyTasks = 1
- alarmEmail, webhookUrl
- useMultiRegionKms = true
- s3ReplicateDeletes = false
- rtoTargetMinutes = 30
- rpoTargetSeconds = 300
- canaryEnabled = false

## Security Considerations

- Separate task execution vs task roles
- SGs with least-privilege access
- KMS key policies allowing services/replication principals
- S3 replication role limited to specific prefixes/buckets
- Step Functions/Lambdas with narrow permissions

## Acceptance Criteria

- With rds-postgres: replica promotion or snapshot restore succeeds
- App reconnects using updated secret
- RTO/RPO recorded in README
- S3 CRR replicates new objects
- Restoring previous versions works in demo
- Dashboard shows replication lag and health
- Alarms fire during GameDay
- Notifications received
- All unit tests pass in CI

## Estimated RPO/RTO

- RPO: 5-10 minutes (last automated backup)
- RTO: 30 minutes (time to promote replica or restore snapshot + app reconfiguration)

## Cost Considerations

- Primary region: Full ECS service, RDS instance
- Secondary region: Standby ECS (1 task), RDS read replica
- S3 storage and replication costs
- CloudWatch, Route 53, Step Functions usage
- Estimated monthly cost: $200-500 depending on usage

## Next Steps

1. Switch to Code mode to implement the CDK application
2. Create reusable constructs for each AWS service
3. Implement stacks for primary and secondary regions
4. Create orchestration workflows
5. Develop tests and documentation
