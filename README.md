# AWS Disaster Recovery - Backup and Restore Pattern

[![Build Status](https://github.com/simoda/AWS-dr-backup-restore/workflows/CI/badge.svg)](https://github.com/simoda/AWS-dr-backup-restore/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/simoda/AWS-dr-backup-restore?include_prereleases)](https://github.com/simoda/AWS-dr-backup-restore/releases)
[![CDK](https://img.shields.io/badge/CDK-v2-orange.svg)](https://docs.aws.amazon.com/cdk/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)

## Overview

A **cost-effective disaster recovery solution** using AWS's Backup and Restore pattern. Delivers 85% cost savings vs warm standby while maintaining enterprise reliability.

**Why This Matters**: Most companies overspend on DR. This pattern provides automated backup/recovery for $30-50/month instead of $300-500/month warm standby.

## Architecture

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

## Key Features

- **Cost Optimized**: $30-50/month vs $300+ warm standby
- **Automated**: Daily backups, cross-region replication, one-click recovery
- **Secure**: KMS encryption, IAM least privilege, audit trails
- **Reliable**: 4-hour RTO/RPO, 99.999999999% durability

## AWS Services

- **AWS Backup**: Cross-region backup orchestration
- **Amazon RDS**: PostgreSQL with point-in-time recovery
- **Amazon S3**: Application data with replication
- **AWS KMS**: Multi-region encryption
- **Amazon ECS**: Containerized application
- **AWS Lambda**: Recovery automation
- **CloudFormation**: Infrastructure as Code

## Quick Start

### Prerequisites

- AWS CLI configured
- Node.js 20+ and AWS CDK v2 (`npm install -g aws-cdk`)
- Python 3.9+ and Poetry (`curl -sSL https://install.python-poetry.org | python3 -`)

### Deploy

```bash
# Clone and setup
git clone https://github.com/simoda/AWS-dr-backup-restore.git
cd AWS-dr-backup-restore/infra

# Install dependencies
poetry install

# Configure (edit cdk.json)
export AWS_ACCOUNT=123456789012
export AWS_REGION=ap-southeast-2

# Deploy
poetry run cdk bootstrap
poetry run cdk deploy --all
```

### Test Recovery

```bash
# Simulate disaster recovery
aws lambda invoke \
  --function-name BackupStack-DeploymentFunction \
  --payload '{"test_mode": true}' response.json
```

## How It Works

1. **Daily Backups**: AWS Backup creates encrypted snapshots
2. **Cross-Region Copy**: Backups replicated to secondary region
3. **Recovery**: Lambda deploys CloudFormation templates in DR region
4. **Data Restore**: RDS point-in-time recovery + S3 sync
5. **Health Checks**: Automated validation of recovered services

## Project Structure

```
infra/
├── app.py                     # Main CDK app
├── stacks/                    # CDK stacks
│   ├── primary_network.py     # VPC, subnets, security
│   ├── primary_data.py        # RDS, S3, KMS
│   ├── primary_app.py         # ECS, ALB
│   └── backup_stack.py        # Backup automation
├── constructs/                # Reusable components
└── templates/                 # Recovery CloudFormation
```

## Technical Details

- **RTO**: 4 hours (infrastructure deployment time)
- **RPO**: 4 hours (backup frequency)
- **Cost**: ~$40/month (vs $300+ warm standby)
- **Encryption**: KMS multi-region keys
- **Monitoring**: CloudWatch alarms + SNS notifications

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed setup and workflow instructions.

```bash
# Quick start
make setup
make lint
make test
make synth
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

Pull requests welcome! Please test CDK synthesis before submitting.
