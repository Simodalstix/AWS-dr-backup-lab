# Testing Strategy for DR Lab

## Overview

This document outlines the comprehensive testing strategy for the Tier-2 Backup & DR Lab implementation, covering unit tests, integration tests, and assertion-based tests.

## Testing Approach

### 1. Unit Testing

#### CDK Construct Tests

- Test each construct can be instantiated correctly
- Test property validation and error handling
- Test method outputs and behavior
- Test resource creation with snapshots

#### Test Files

- `test_kms_multi_region_key.py`
- `test_ecs_service_alb.py`
- `test_rds_with_replica.py`
- `test_s3_replication_pair.py`
- `test_dashboards_alarms.py`
- `test_stepfunctions_failover.py`

#### Test Framework

- Use pytest for test execution
- Use CDK assertions library for resource validation
- Mock AWS services where appropriate

### 2. Integration Testing

#### Stack Wiring Tests

- Test stack outputs are correctly passed as inputs
- Test cross-stack references work correctly
- Test security group rules are properly configured
- Test IAM permissions are correctly scoped

#### Test Files

- `test_primary_stacks_wiring.py`
- `test_secondary_stacks_wiring.py`
- `test_global_stacks_wiring.py`
- `test_cross_region_connectivity.py`

### 3. Assertion-Based Testing

#### Critical Resource Assertions

- Route 53 failover record created with health check on primary
- S3 buckets versioned with replication configuration when enabled
- RDS global/replica resources exist depending on dbMode
- Alarms created for ReplicaLag & Health checks
- Step Functions has expected states per chosen mode

#### Test Files

- `test_dr_wiring.py`
- `test_security_configurations.py`
- `test_networking_configurations.py`

## Test Implementation Details

### CDK Assertions Library Usage

#### Example Test for ECS Service Construct

```python
def test_ecs_service_creation():
    # GIVEN
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")

    # WHEN
    ecs_service = ECSServiceALB(
        stack, "TestECS",
        vpc=vpc,
        cluster=cluster,
        image="nginx:latest"
    )

    # THEN
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::ECS::Service", {
        "DesiredCount": 2,
        "LaunchType": "FARGATE"
    })
```

#### Example Test for S3 Replication

```python
def test_s3_replication_configured():
    # GIVEN
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")

    # WHEN
    s3_pair = S3ReplicationPair(
        stack, "TestS3",
        source_region="ap-southeast-2",
        destination_region="us-west-2",
        bucket_name_prefix="dr-lab"
    )

    # THEN
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::S3::Bucket", {
        "VersioningConfiguration": {
            "Status": "Enabled"
        }
    })
```

### Test Environment Setup

#### Dependencies

- Install pytest: `pip install pytest`
- Install CDK assertions: Included with CDK
- Install moto for mocking: `pip install moto`

#### Test Execution

- Run all tests: `pytest tests/`
- Run specific test: `pytest tests/test_dr_wiring.py`
- Run with coverage: `pytest --cov=constructs tests/`

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: CI Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r infra/requirements.txt
      - name: Run tests
        run: |
          cd infra
          pytest tests/
```

### Test Coverage Requirements

- Minimum 80% code coverage for constructs
- 100% coverage for critical wiring assertions
- All security configurations must be tested
- All networking configurations must be tested

## Test Data and Fixtures

### Reusable Fixtures

```python
@pytest.fixture
def vpc():
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    return ec2.Vpc(stack, "TestVpc")

@pytest.fixture
def cluster(vpc):
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    return ecs.Cluster(stack, "TestCluster", vpc=vpc)
```

## Performance and Load Testing

### GameDay Simulation Tests

- Simulate primary region outage
- Measure failover time (RTO)
- Verify data consistency (RPO)
- Test notification systems

### Test Scenarios

1. Primary ECS service failure
2. Primary RDS instance failure
3. Primary S3 bucket deletion
4. Network partition between regions

## Security Testing

### IAM Policy Validation

- Test IAM policies are least-privilege
- Test KMS key policies allow required services
- Test S3 bucket policies restrict access

### Encryption Testing

- Verify KMS encryption is enabled
- Verify TLS is enforced for connections
- Verify secrets are properly encrypted

## Documentation Testing

### README Validation

- Verify all commands are executable
- Verify architecture diagram is current
- Verify RPO/RTO values are documented
- Verify cost estimates are accurate

## Test Maintenance

### Regular Review

- Review tests when modifying constructs
- Update tests when adding new features
- Remove obsolete tests when deprecating features

### Test Refactoring

- Keep tests readable and maintainable
- Remove duplication between tests
- Update test data and fixtures regularly

## Quality Gates

### Pre-Deployment Checks

- All unit tests must pass
- Minimum code coverage must be achieved
- Security tests must pass
- Critical wiring assertions must pass

### Post-Deployment Validation

- Verify resources are created correctly
- Verify cross-region replication is working
- Verify monitoring and alerting is configured
- Verify failover procedures work as expected
