# Runbooks and GameDay Scenarios

## Overview

This document provides detailed runbooks for disaster recovery operations and GameDay scenarios for testing the DR capabilities of the Tier-2 Backup & DR Lab.

## Runbooks

### 1. Planned Failover (RDS Standard)

#### Purpose

Execute a planned failover from primary to secondary region during a maintenance window.

#### Prerequisites

- Secondary region ECS service is running (warm standby)
- RDS read replica is healthy and in sync
- Route 53 health checks are operational
- Step Functions state machine is deployed

#### Steps

1. **Pre-failover Validation**

   ```bash
   # Check RDS replica lag
   aws rds describe-db-instances --db-instance-identifier dr-lab-replica --region us-west-2 \
     --query 'DBInstances[0].StatusInfos[?StatusType==`read replication`].Status'

   # Check ECS service health in secondary
   aws ecs describe-services --cluster dr-lab-secondary --services dr-lab-service --region us-west-2

   # Verify Route 53 health check status
   aws route53 get-health-check-status --health-check-id <health-check-id>
   ```

2. **Initiate Failover**

   ```bash
   # Start Step Functions execution
   aws stepfunctions start-execution \
     --state-machine-arn arn:aws:states:ap-southeast-2:ACCOUNT:stateMachine:dr-lab-failover \
     --input '{"mode":"planned","reason":"maintenance"}'
   ```

3. **Monitor Failover Progress**

   ```bash
   # Monitor execution
   aws stepfunctions describe-execution --execution-arn <execution-arn>

   # Check logs
   aws logs filter-log-events --log-group-name /aws/stepfunctions/dr-lab-failover
   ```

4. **Post-failover Validation**

   ```bash
   # Test application endpoint
   curl -f https://app.example.com/healthz

   # Test database connectivity
   curl -f https://app.example.com/dbcheck

   # Verify write operations
   curl -X POST https://app.example.com/test-write -d '{"test":"data"}'
   ```

#### Expected RTO

- **Target**: 30 minutes
- **Breakdown**:
  - RDS replica promotion: 5-10 minutes
  - ECS service scaling: 2-5 minutes
  - Route 53 propagation: 1-2 minutes
  - Application startup: 2-3 minutes
  - Validation: 5 minutes

#### Expected RPO

- **Target**: 5-10 minutes (last automated backup)
- **Actual**: Time since last RDS backup

### 2. Unplanned Failover (Emergency)

#### Purpose

Execute emergency failover when primary region is unavailable.

#### Trigger Conditions

- Primary region health check fails
- Primary RDS instance is unavailable
- Primary ECS service is down
- Network connectivity issues

#### Steps

1. **Assess Situation**

   ```bash
   # Check primary region status
   aws ecs describe-services --cluster dr-lab-primary --services dr-lab-service --region ap-southeast-2

   # Check RDS primary status
   aws rds describe-db-instances --db-instance-identifier dr-lab-primary --region ap-southeast-2

   # Check Route 53 health
   aws route53 get-health-check-status --health-check-id <health-check-id>
   ```

2. **Manual Failover (if Step Functions unavailable)**

   ```bash
   # Promote RDS replica
   aws rds promote-read-replica --db-instance-identifier dr-lab-replica --region us-west-2

   # Scale ECS service
   aws ecs update-service --cluster dr-lab-secondary --service dr-lab-service \
     --desired-count 2 --region us-west-2

   # Update Route 53 record (if needed)
   aws route53 change-resource-record-sets --hosted-zone-id <zone-id> \
     --change-batch file://failover-record-change.json
   ```

3. **Update Application Configuration**

   ```bash
   # Update Secrets Manager with new DB endpoint
   aws secretsmanager update-secret --secret-id dr-lab-db-secret \
     --secret-string '{"host":"dr-lab-replica.region.rds.amazonaws.com","username":"admin","password":"..."}' \
     --region us-west-2

   # Restart ECS tasks to pick up new configuration
   aws ecs update-service --cluster dr-lab-secondary --service dr-lab-service \
     --force-new-deployment --region us-west-2
   ```

#### Recovery Time Objectives

- **Detection**: 5 minutes (health check interval)
- **Decision**: 5 minutes (manual assessment)
- **Execution**: 20-30 minutes
- **Total RTO**: 30-40 minutes

### 3. Database Restore from Snapshot

#### Purpose

Restore database from automated backup when read replica is not available.

#### When to Use

- Read replica is corrupted or unavailable
- Need to restore to specific point in time
- Cross-region replica creation failed

#### Steps

1. **Identify Latest Snapshot**

   ```bash
   # List available snapshots
   aws rds describe-db-snapshots --db-instance-identifier dr-lab-primary \
     --snapshot-type automated --region ap-southeast-2 \
     --query 'DBSnapshots[0].{SnapshotId:DBSnapshotIdentifier,CreateTime:SnapshotCreateTime}'
   ```

2. **Restore Database**

   ```bash
   # Restore from snapshot
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier dr-lab-restored \
     --db-snapshot-identifier <snapshot-id> \
     --db-instance-class db.t3.micro \
     --region us-west-2
   ```

3. **Update Application**
   ```bash
   # Update secret with new endpoint
   aws secretsmanager update-secret --secret-id dr-lab-db-secret \
     --secret-string '{"host":"dr-lab-restored.region.rds.amazonaws.com","username":"admin","password":"..."}' \
     --region us-west-2
   ```

#### Expected RTO

- **Snapshot restore**: 20-45 minutes (depending on size)
- **Application update**: 5 minutes
- **Total**: 25-50 minutes

#### Expected RPO

- **Automated backup interval**: Up to 24 hours
- **Point-in-time recovery**: Up to 5 minutes

### 4. S3 Object Recovery (Undelete/Version Restore)

#### Purpose

Recover deleted or corrupted objects from S3 using versioning.

#### Scenarios

- Accidental object deletion
- Object corruption
- Ransomware attack simulation

#### Steps

1. **List Object Versions**

   ```bash
   # List all versions of an object
   aws s3api list-object-versions --bucket dr-lab-app-data-primary \
     --prefix "important-file.json"
   ```

2. **Restore Previous Version**

   ```bash
   # Copy previous version to current
   aws s3api copy-object --bucket dr-lab-app-data-primary \
     --copy-source "dr-lab-app-data-primary/important-file.json?versionId=<version-id>" \
     --key "important-file.json"
   ```

3. **Restore from Replica Bucket**
   ```bash
   # Copy from replicated bucket
   aws s3 cp s3://dr-lab-app-data-secondary/important-file.json \
     s3://dr-lab-app-data-primary/important-file.json
   ```

#### Recovery Time

- **Version restore**: < 1 minute
- **Cross-region copy**: 1-5 minutes (depending on size)

### 5. Failback Procedure

#### Purpose

Return operations to primary region after issue resolution.

#### Prerequisites

- Primary region issues resolved
- Primary infrastructure healthy
- Data synchronization completed

#### Steps

1. **Prepare Primary Region**

   ```bash
   # Ensure primary ECS service is ready
   aws ecs update-service --cluster dr-lab-primary --service dr-lab-service \
     --desired-count 2 --region ap-southeast-2

   # Create new RDS instance if needed
   aws rds create-db-instance --db-instance-identifier dr-lab-primary-new \
     --db-instance-class db.t3.micro --engine postgres --region ap-southeast-2
   ```

2. **Synchronize Data**

   ```bash
   # Create database dump from secondary
   pg_dump -h dr-lab-replica.region.rds.amazonaws.com -U admin dbname > failback.sql

   # Restore to primary
   psql -h dr-lab-primary-new.region.rds.amazonaws.com -U admin dbname < failback.sql
   ```

3. **Switch Traffic Back**
   ```bash
   # Update Route 53 to point back to primary
   aws route53 change-resource-record-sets --hosted-zone-id <zone-id> \
     --change-batch file://failback-record-change.json
   ```

## GameDay Scenarios

### GameDay 1: Primary Region Outage

#### Objective

Simulate complete primary region failure and measure failover capabilities.

#### Scenario Setup

```bash
# Stop ECS service in primary
aws ecs update-service --cluster dr-lab-primary --service dr-lab-service \
  --desired-count 0 --region ap-southeast-2

# Simulate RDS failure by modifying security group
aws ec2 revoke-security-group-ingress --group-id <db-sg-id> \
  --protocol tcp --port 5432 --source-group <app-sg-id> --region ap-southeast-2
```

#### Success Criteria

- Route 53 detects failure within 5 minutes
- Automatic failover to secondary region
- Application accessible within 30 minutes
- Database writes successful in secondary
- Monitoring alerts triggered

#### Measurements

- **Detection Time**: Time until health check fails
- **Failover Time**: Time until secondary is serving traffic
- **Data Loss**: Amount of data lost (RPO)
- **Total Downtime**: End-to-end RTO

### GameDay 2: Database Snapshot Restore

#### Objective

Test database recovery from automated snapshots.

#### Scenario Setup

```bash
# Delete read replica to simulate unavailability
aws rds delete-db-instance --db-instance-identifier dr-lab-replica \
  --skip-final-snapshot --region us-west-2
```

#### Success Criteria

- Latest snapshot identified correctly
- Database restored within 45 minutes
- Application connects to restored database
- Data integrity verified

#### Measurements

- **Snapshot Age**: How old was the restored snapshot
- **Restore Time**: Time to complete database restore
- **Data Verification**: Confirm data integrity

### GameDay 3: S3 Ransomware Simulation

#### Objective

Simulate ransomware attack on S3 data and test recovery procedures.

#### Scenario Setup

```bash
# Delete critical objects
aws s3 rm s3://dr-lab-app-data-primary/critical-data/ --recursive

# Overwrite objects with "encrypted" content
echo "ENCRYPTED_BY_RANSOMWARE" | aws s3 cp - s3://dr-lab-app-data-primary/important-file.json
```

#### Success Criteria

- Previous versions can be restored
- Cross-region replica data is intact
- Application functionality restored
- Recovery time under 10 minutes

#### Measurements

- **Detection Time**: Time to detect data corruption
- **Recovery Time**: Time to restore all affected objects
- **Data Loss**: Amount of data that couldn't be recovered

## Post-GameDay Activities

### 1. Results Documentation

- Record actual vs. target RTO/RPO
- Document any issues encountered
- Identify improvement opportunities

### 2. Process Improvements

- Update runbooks based on lessons learned
- Improve automation where manual steps were required
- Enhance monitoring and alerting

### 3. Team Training

- Conduct post-mortem sessions
- Update team training materials
- Schedule regular GameDay exercises

## Monitoring During GameDays

### Key Metrics to Track

- Route 53 health check status
- ECS service task count and health
- RDS connection count and lag
- S3 replication metrics
- Application response times
- Error rates and success rates

### Alerting Validation

- Verify all expected alerts are triggered
- Confirm notification delivery
- Test escalation procedures
- Validate alert content and clarity
