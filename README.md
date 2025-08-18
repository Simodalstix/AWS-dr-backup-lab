# AWS Disaster Recovery Lab - Backup and Restore Pattern

## Overview

This project demonstrates a **modern, enterprise-ready disaster recovery solution** using AWS's recommended **Backup and Restore** pattern. This architecture provides cost-effective, automated disaster recovery while maintaining enterprise-grade reliability and following AWS Well-Architected principles.

## Why Backup and Restore?

### Architecture Decision

We chose the **Backup and Restore** pattern because it delivers:

- **Cost Optimization**: 85-90% cost savings compared to warm standby patterns
- **Enterprise Reliability**: AWS-managed backup services with 99.999999999% (11 9's) durability
- **Automation-First**: Fully automated backup, recovery, and infrastructure deployment
- **Compliance Ready**: Built-in encryption, audit trails, and retention policies
- **Scalable**: Handles workloads from startup to enterprise scale

### Pattern Comparison

| Pattern              | RTO       | RPO       | Monthly Cost | Use Case                         |
| -------------------- | --------- | --------- | ------------ | -------------------------------- |
| **Backup & Restore** | 2-4 hours | 1-4 hours | **$30-50**   | Cost-sensitive, planned recovery |
| Pilot Light          | 30-60 min | 15-30 min | $150-300     | Balanced cost/recovery           |
| Warm Standby         | 5-15 min  | 5-15 min  | $300-500     | Mission-critical, fast recovery  |
| Multi-Site Active    | < 1 min   | Near-zero | $800+        | Zero-downtime requirements       |

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    PRIMARY REGION                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Network   │  │ Application │  │       Data          │ │
│  │    Stack    │  │    Stack    │  │      Stack          │ │
│  │             │  │             │  │                     │ │
│  │ • VPC       │  │ • ECS       │  │ • RDS PostgreSQL    │ │
│  │ • Subnets   │  │ • ALB       │  │ • S3 Buckets        │ │
│  │ • Security  │  │ • Auto      │  │ • KMS Encryption    │ │
│  │   Groups    │  │   Scaling   │  │ • Backup Policies   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Automated Backups
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 BACKUP & RECOVERY SYSTEM                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ AWS Backup  │  │ CloudFormation │  │   Automation      │ │
│  │   Service   │  │   Templates    │  │    Lambda         │ │
│  │             │  │                │  │                   │ │
│  │ • Cross-    │  │ • Network      │  │ • Deployment      │ │
│  │   Region    │  │   Template     │  │   Orchestration   │ │
│  │ • Encrypted │  │ • App Template │  │ • Parameter       │ │
│  │ • Scheduled │  │ • Recovery     │  │   Management      │ │
│  │ • Validated │  │   Runbooks     │  │ • Health Checks   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### AWS Services Used

- **AWS Backup**: Centralized backup across services
- **Amazon RDS**: PostgreSQL with automated backups
- **Amazon S3**: Application data with cross-region replication
- **AWS KMS**: Multi-region encryption keys
- **Amazon ECS**: Containerized application platform
- **Application Load Balancer**: High-availability load balancing
- **AWS Lambda**: Serverless automation functions
- **AWS Systems Manager**: Parameter and automation management
- **Amazon CloudWatch**: Monitoring and alerting

## Key Features

### 🔒 Enterprise Security

- **Encryption at Rest**: KMS-encrypted backups and data
- **Encryption in Transit**: TLS 1.2+ for all communications
- **IAM Least Privilege**: Role-based access controls
- **Audit Logging**: CloudTrail integration for compliance

### 🚀 Automation-First Design

- **Scheduled Backups**: Daily automated backups with retention policies
- **Cross-Region Replication**: Automatic backup copying to secondary region
- **Infrastructure as Code**: Complete CDK-based deployment
- **Recovery Automation**: One-click disaster recovery deployment

### 💰 Cost Optimized

- **Pay-per-Use**: No always-running secondary infrastructure
- **Intelligent Tiering**: Automatic backup lifecycle management
- **Resource Optimization**: Right-sized instances and storage
- **Monitoring**: Cost tracking and optimization alerts

### 📊 Observability

- **Backup Monitoring**: Success/failure tracking and alerting
- **Recovery Testing**: Automated backup validation
- **Performance Metrics**: RTO/RPO measurement and reporting
- **Health Dashboards**: Real-time system status

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- AWS CDK v2 installed (`npm install -g aws-cdk`)
- Python 3.9+ with pip

### Deployment

```bash
# Clone the repository
git clone <repository-url>
cd AWS-dr-backup-lab

# Install dependencies
cd infra
pip install -r requirements.txt

# Configure your environment
export AWS_ACCOUNT=123456789012
export AWS_REGION=ap-southeast-2

# Deploy the infrastructure
cdk bootstrap
cdk deploy --all

# Verify deployment
aws backup list-backup-plans
aws ecs list-clusters
```

### Configuration

Edit [`cdk.json`](infra/cdk.json) to customize:

```json
{
  "context": {
    "config": {
      "primary_region": "ap-southeast-2",
      "secondary_region": "us-west-2",
      "rto_target_hours": 4,
      "rpo_target_hours": 4,
      "alarm_email": "admin@yourcompany.com"
    }
  }
}
```

## Disaster Recovery Process

### Automated Recovery Workflow

1. **Detection**: Manual trigger or automated failure detection
2. **Parameter Retrieval**: Latest backup identifiers from Systems Manager
3. **Infrastructure Deployment**: CloudFormation templates in secondary region
4. **Data Restoration**: RDS point-in-time recovery, S3 data sync
5. **Application Startup**: ECS service deployment with health checks
6. **DNS Failover**: Route 53 health check-based failover

### Recovery Commands

```bash
# Test recovery (dry-run)
aws lambda invoke \
  --function-name BackupStack-DeploymentFunction \
  --payload '{"test_mode": true, "target_region": "us-west-2"}' \
  response.json

# Execute full recovery
aws lambda invoke \
  --function-name BackupStack-DeploymentFunction \
  --payload '{"execute_recovery": true, "target_region": "us-west-2"}' \
  response.json

# Monitor recovery progress
aws logs tail /aws/lambda/BackupStack-DeploymentFunction --follow
```

## Project Structure

```
infra/
├── app.py                     # Main CDK application
├── constructs/                # Reusable CDK constructs
│   ├── backup_plan.py         # AWS Backup integration
│   ├── deployment_automation.py # Recovery automation
│   ├── ecs_service_alb.py     # Application platform
│   ├── kms_multi_region_key.py # Encryption keys
│   ├── rds_with_replica.py    # Database with backups
│   ├── recovery_parameters.py # Configuration management
│   ├── s3_replication_pair.py # Data storage and sync
│   └── template_storage.py    # CloudFormation templates
├── stacks/                    # CDK stack definitions
│   ├── backup_stack.py        # Backup and recovery stack
│   ├── primary_app.py         # Application infrastructure
│   ├── primary_data.py        # Data layer infrastructure
│   └── primary_network.py     # Network infrastructure
└── templates/                 # Recovery templates
    ├── application-template.json
    └── network-template.json
```

## Best Practices Implemented

### AWS Well-Architected Framework

- **Operational Excellence**: Infrastructure as Code, automated deployments
- **Security**: Encryption, least privilege, audit logging
- **Reliability**: Multi-AZ deployment, automated backups, health checks
- **Performance Efficiency**: Right-sized resources, monitoring
- **Cost Optimization**: Pay-per-use model, lifecycle policies

### Disaster Recovery Best Practices

- **Regular Testing**: Automated backup validation and recovery drills
- **Documentation**: Comprehensive runbooks and procedures
- **Monitoring**: Proactive alerting and health checks
- **Automation**: Minimize manual intervention during recovery

## Monitoring and Alerting

### Key Metrics

- Backup success rate (target: 99.9%)
- Recovery Time Objective (target: < 4 hours)
- Recovery Point Objective (target: < 4 hours)
- Cost per month (target: < $50)

### Alerts

- Backup job failures
- Cross-region replication delays
- Recovery automation errors
- Cost threshold breaches

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following AWS best practices
4. Test thoroughly including disaster recovery scenarios
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or support:

- Create an issue in this repository
- Review AWS Backup documentation
- Consult AWS Well-Architected Framework guides
