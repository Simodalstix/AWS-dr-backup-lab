.PHONY: help install lint test synth deploy clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	cd infra && poetry install

format: ## Format code with black and isort
	cd infra && poetry run black .
	cd infra && poetry run isort .

lint: format ## Alias for format (kept for compatibility)

test: ## Run tests
	cd infra && poetry run pytest -v

synth: ## Synthesize CDK templates
	cd infra && poetry run cdk synth

deploy: ## Deploy all stacks
	cd infra && poetry run cdk deploy --all --require-approval never

bootstrap: ## Bootstrap CDK
	cd infra && poetry run cdk bootstrap

clean: ## Clean generated files
	cd infra && rm -rf cdk.out .pytest_cache __pycache__
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

setup: install bootstrap ## Initial setup (install + bootstrap)