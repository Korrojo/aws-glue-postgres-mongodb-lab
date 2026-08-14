.DEFAULT_GOAL := help

RUFF ?= ruff
PYTEST ?= pytest

.PHONY: help check format-check lint unit-test compose-check terraform-check \
	local-up local-status local-test local-down \
	doctor infra-init infra-plan infra-apply secrets-put ec2-bootstrap \
	deploy crawl run validate rerun-test cost-check destroy-lab

help: ## Show governance checks and roadmap-owned future targets.
	@printf '%s\n' \
		'Safe local governance checks:' \
		'  make check             Run all currently safe checks' \
		'  make format-check      Check Python formatting' \
		'  make lint              Lint Python files' \
		'  make unit-test         Run governance/unit tests' \
		'  make compose-check     Validate Compose when GLUE-010 adds it' \
		'  make terraform-check   Format/validate Terraform when GLUE-020 adds it' \
		'' \
		'Future operational targets fail with their owning roadmap task.'

check: format-check lint unit-test ## Run every implemented safe local check.

format-check: ## Check Python formatting without modifying files.
	@$(RUFF) format --check .

lint: ## Lint Python files without modifying files.
	@$(RUFF) check .

unit-test: ## Run governance and unit tests without AWS or containers.
	@$(PYTEST) tests/unit -q

compose-check: ## Validate Compose syntax after GLUE-010 supplies configuration.
	@if [ ! -f docker/compose.yaml ]; then \
		printf '%s\n' 'ERROR: make compose-check is not implemented; GLUE-010 must add docker/compose.yaml.' >&2; \
		exit 2; \
	fi; \
	if ! command -v docker >/dev/null 2>&1; then \
		printf '%s\n' 'ERROR: docker is required to validate docker/compose.yaml.' >&2; \
		exit 2; \
	fi; \
	docker compose -f docker/compose.yaml config --quiet

terraform-check: ## Format and validate Terraform after GLUE-020 supplies configuration.
	@set -- infrastructure/terraform/*.tf; \
	if [ ! -e "$$1" ]; then \
		printf '%s\n' 'ERROR: make terraform-check is not implemented; GLUE-020 must add Terraform configuration.' >&2; \
		exit 2; \
	fi; \
	if ! command -v terraform >/dev/null 2>&1; then \
		printf '%s\n' 'ERROR: terraform is required to validate infrastructure/terraform.' >&2; \
		exit 2; \
	fi; \
	terraform -chdir=infrastructure/terraform fmt -check -recursive; \
	terraform -chdir=infrastructure/terraform init -backend=false -input=false; \
	terraform -chdir=infrastructure/terraform validate

define fail_not_implemented
	@printf '%s\n' 'ERROR: make $@ is not implemented; owned by roadmap task $(1).' >&2
	@exit 2
endef

local-up local-status local-test local-down:
	$(call fail_not_implemented,GLUE-010)

doctor infra-init infra-plan infra-apply secrets-put ec2-bootstrap:
	$(call fail_not_implemented,GLUE-020)

deploy crawl:
	$(call fail_not_implemented,GLUE-030)

run:
	$(call fail_not_implemented,GLUE-040)

validate rerun-test:
	$(call fail_not_implemented,GLUE-050)

cost-check destroy-lab:
	$(call fail_not_implemented,GLUE-060)
