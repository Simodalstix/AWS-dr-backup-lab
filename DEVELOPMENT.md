# Development Guide

## Quick Setup

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Clone and setup
git clone https://github.com/simoda/AWS-dr-backup-restore.git
cd AWS-dr-backup-restore

# Install dependencies and bootstrap
make setup
```

## Development Workflow

```bash
# Format and lint code
make lint

# Run tests
make test

# Synthesize templates (check for errors)
make synth

# Deploy to AWS
make deploy
```

## Configuration

Edit `infra/cdk.json` to customize:
- AWS regions
- Database settings  
- Application configuration
- Backup policies

## Environment Variables

Create `.env` file in project root:
```bash
AWS_ACCOUNT=820242933814
AWS_REGION=ap-southeast-2
ALARM_EMAIL=your-email@example.com
```

## Testing Recovery

```bash
# Simulate disaster recovery
aws lambda invoke \
  --function-name BackupStack-DeploymentFunction \
  --payload '{"test_mode": true}' response.json
```

## Project Structure

- `infra/stacks/` - CDK stack definitions
- `infra/constructs/` - Reusable CDK constructs  
- `infra/templates/` - CloudFormation templates for recovery
- `tests/` - Unit tests

## Troubleshooting

**CDK Bootstrap Issues:**
```bash
cdk bootstrap --trust 123456789012 --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess
```

**Permission Errors:**
Ensure your AWS credentials have sufficient permissions for all services used.