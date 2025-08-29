# Contributing

## Development Setup

1. Install Python 3.9+ and Poetry
2. Install Node.js 20+ and AWS CDK v2
3. Clone the repo and run:

```bash
cd infra
poetry install
```

## Making Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally:

```bash
# Lint and format
poetry run black .
poetry run flake8 .
poetry run isort .

# Test CDK synthesis
poetry run cdk synth

# Run tests
poetry run pytest
```

5. Submit a pull request

## Guidelines

- Keep changes focused and atomic
- Test CDK synthesis before submitting
- Follow existing code style (Black + Flake8)
- Update documentation if needed

## Issues

- Use GitHub Issues for bugs and feature requests
- Include CDK version and Python version in bug reports
- Provide minimal reproduction steps