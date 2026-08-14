.DEFAULT_GOAL := help

RUFF ?= ruff
PYTEST ?= pytest
COMPOSE_FILE := docker/compose.yaml
COMPOSE := docker compose --env-file .env -f $(COMPOSE_FILE)

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
		'  make compose-check     Validate Compose without starting containers' \
		'  make local-up          Start PostgreSQL and MongoDB and wait for health' \
		'  make local-status      Show container status' \
		'  make local-test        Run source, invalid-fixture, and target assertions' \
		'  make local-down        Stop containers; add RESET_VOLUMES=1 to reseed' \
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

compose-check: ## Validate Compose syntax with generated throwaway credentials.
	@if ! command -v docker >/dev/null 2>&1; then \
		printf '%s\n' 'ERROR: docker is required to validate docker/compose.yaml.' >&2; \
		exit 2; \
	fi
	@./scripts/compose-check.sh

local-up: ## Start both databases and wait for healthy containers.
	@test -f .env || { printf '%s\n' 'ERROR: copy .env.example to .env and set all password values.' >&2; exit 2; }
	@$(COMPOSE) config --quiet
	@$(COMPOSE) up -d --wait --wait-timeout 180

local-status: ## Show current database container state.
	@test -f .env || { printf '%s\n' 'ERROR: .env is required for Compose interpolation.' >&2; exit 2; }
	@$(COMPOSE) ps

local-test: ## Run deterministic source, failure-fixture, and empty-target checks.
	@test -f .env || { printf '%s\n' 'ERROR: .env is required for data-layer tests.' >&2; exit 2; }
	@./scripts/test-local-data.sh

local-down: ## Stop containers; set RESET_VOLUMES=1 to remove only project volumes.
	@test -f .env || { printf '%s\n' 'ERROR: .env is required for exact Compose project resolution.' >&2; exit 2; }
	@if [ "$(RESET_VOLUMES)" = "1" ]; then \
		$(COMPOSE) down --volumes --remove-orphans; \
	else \
		$(COMPOSE) down --remove-orphans; \
	fi

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
