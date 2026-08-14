.DEFAULT_GOAL := help

RUFF ?= ruff
PYTEST ?= pytest
TERRAFORM ?= terraform
TF_ROOT := infrastructure/terraform
COMPOSE_FILE := docker/compose.yaml
COMPOSE := docker compose --env-file .env -f $(COMPOSE_FILE)

.PHONY: help check format-check lint unit-test compose-check terraform-check \
	local-up local-status local-test local-down \
	doctor infra-init infra-plan infra-apply secrets-put ec2-bootstrap ec2-reset-data \
	deploy crawl run validate rerun-test cost-check destroy-plan destroy-lab

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
		'  make terraform-check   Validate and mock-test the AWS foundation' \
		'  make doctor            Verify personal AWS and local prerequisites' \
		'  make infra-init        Initialize pinned Terraform providers' \
		'  make infra-plan        Save a reviewable local lab plan' \
		'  make infra-apply       Apply only after APPROVE_LAB_APPLY=1' \
		'  make secrets-put       Generate and store both database secrets' \
		'  make ec2-bootstrap     Start/test databases through SSM' \
		'  make ec2-reset-data    Reset only this project data after secret rotation' \
		'  make destroy-plan      Save a review-bound Terraform destroy plan' \
		'  make destroy-lab       Apply only after APPROVE_LAB_DESTROY=1' \
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
		$(COMPOSE) down --volumes; \
	else \
		$(COMPOSE) down --remove-orphans; \
	fi

terraform-check: ## Format-check, validate, and mock-plan the Terraform root.
	@$(TERRAFORM) -chdir=$(TF_ROOT) fmt -check -recursive
	@$(TERRAFORM) -chdir=$(TF_ROOT) init -backend=false -input=false
	@$(TERRAFORM) -chdir=$(TF_ROOT) validate
	@$(TERRAFORM) -chdir=$(TF_ROOT) test

doctor: ## Verify repository, personal AWS identity, Region, and tools.
	@TERRAFORM="$(TERRAFORM)" ./scripts/doctor.sh

infra-init: ## Initialize the pinned providers using local state.
	@$(TERRAFORM) -chdir=$(TF_ROOT) init -input=false

infra-plan: ## Save a reviewable plan bound to the personal account and current Git SHA.
	@AWS_PROFILE="$(AWS_PROFILE)" AWS_REGION="$(AWS_REGION)" TERRAFORM="$(TERRAFORM)" ./scripts/terraform-plan.sh

infra-apply: ## Apply only the account/Region/Git/hash-bound reviewed plan.
	@APPROVE_LAB_APPLY="$(APPROVE_LAB_APPLY)" AWS_PROFILE="$(AWS_PROFILE)" AWS_REGION="$(AWS_REGION)" TERRAFORM="$(TERRAFORM)" ./scripts/terraform-apply.sh

secrets-put: ## Generate fresh values and store them without printing them.
	@AWS_PROFILE="$(AWS_PROFILE)" AWS_REGION="$(AWS_REGION)" TERRAFORM="$(TERRAFORM)" ./scripts/put-lab-secrets.sh

ec2-bootstrap: ## Start and validate the databases through SSM.
	@AWS_PROFILE="$(AWS_PROFILE)" AWS_REGION="$(AWS_REGION)" TERRAFORM="$(TERRAFORM)" ./scripts/run-ssm-bootstrap.sh

ec2-reset-data: ## Remove only this Compose project's data, then reseed and test through SSM.
	@RESET_DATA="1" AWS_PROFILE="$(AWS_PROFILE)" AWS_REGION="$(AWS_REGION)" TERRAFORM="$(TERRAFORM)" ./scripts/run-ssm-bootstrap.sh

destroy-plan: ## Save a destroy plan bound to exact project, state, identity, and Git SHA.
	@AWS_PROFILE="$(AWS_PROFILE)" AWS_REGION="$(AWS_REGION)" TERRAFORM="$(TERRAFORM)" ./scripts/terraform-destroy-plan.sh

destroy-lab: ## Apply only the reviewed destroy plan after explicit approval.
	@APPROVE_LAB_DESTROY="$(APPROVE_LAB_DESTROY)" AWS_PROFILE="$(AWS_PROFILE)" AWS_REGION="$(AWS_REGION)" TERRAFORM="$(TERRAFORM)" ./scripts/terraform-destroy.sh

define fail_not_implemented
	@printf '%s\n' 'ERROR: make $@ is not implemented; owned by roadmap task $(1).' >&2
	@exit 2
endef

deploy crawl:
	$(call fail_not_implemented,GLUE-030)

run:
	$(call fail_not_implemented,GLUE-040)

validate rerun-test:
	$(call fail_not_implemented,GLUE-050)

cost-check:
	$(call fail_not_implemented,GLUE-060)
