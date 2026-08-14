from __future__ import annotations

import importlib.util
import logging
import os
import re
import shutil
import subprocess
import sys
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TF_ROOT = ROOT / "infrastructure/terraform"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def test_terraform_defines_credential_free_on_demand_glue_topology() -> None:
    terraform = read("infrastructure/terraform/main.tf")
    outputs = read("infrastructure/terraform/outputs.tf")
    mock_tests = read("infrastructure/terraform/tests/foundation.tftest.hcl")

    for resource in (
        'resource "aws_glue_catalog_database" "lab"',
        'resource "aws_glue_connection" "postgres"',
        'resource "aws_glue_connection" "mongodb"',
        'resource "aws_glue_crawler" "orders"',
        'resource "aws_glue_job" "orders_to_mongodb"',
    ):
        assert resource in terraform
    assert 'connection_type = "JDBC"' in terraform
    assert 'connection_type = "MONGODB"' in terraform
    assert "SECRET_ID           = aws_secretsmanager_secret.postgres.name" in terraform
    assert "SECRET_ID      = aws_secretsmanager_secret.mongodb_glue.name" in terraform
    assert 'resource "aws_secretsmanager_secret" "mongodb_glue"' in terraform
    ec2_secret_policy = terraform.split('data "aws_iam_policy_document" "ec2_secrets"', 1)[1].split(
        'resource "aws_iam_role_policy" "ec2_secrets"', 1
    )[0]
    assert "aws_secretsmanager_secret.mongodb.arn" in ec2_secret_policy
    assert "aws_secretsmanager_secret.mongodb_glue.arn" in ec2_secret_policy
    glue_access = terraform.split('data "aws_iam_policy_document" "glue_lab_access"', 1)[1]
    glue_secret_policy = glue_access.split("ReadLabDatabaseSecrets", 1)[1].split("}\n}", 1)[0]
    assert "aws_secretsmanager_secret.mongodb_glue.arn" in glue_secret_policy
    assert "aws_secretsmanager_secret.mongodb.arn" not in glue_secret_policy
    assert "USERNAME" not in terraform
    assert "PASSWORD" not in terraform
    assert len(re.findall(r"subnet_id\s+=\s+aws_subnet\.lab\.id", terraform)) >= 2
    assert (
        len(
            re.findall(
                r"security_group_id_list\s+=\s+\[aws_security_group\.glue\.id\]",
                terraform,
            )
        )
        == 2
    )
    assert re.search(r'path\s+=\s+"sales_lab/sales/orders"', terraform)
    assert re.search(r'path\s+=\s+"sales_lab/sales/order_items"', terraform)
    assert "schedule" not in _resource_block(terraform, "aws_glue_crawler", "orders")
    assert re.search(r'glue_version\s+=\s+"5\.1"', terraform)
    assert re.search(r'worker_type\s+=\s+"G\.1X"', terraform)
    assert re.search(r"number_of_workers\s+=\s+2", terraform)
    assert "ReadLabArtifactObjects" in terraform
    assert "${aws_s3_bucket.artifacts.arn}/glue/artifacts/*" in terraform
    assert "UseLabTemporaryObjects" in terraform
    assert "${aws_s3_bucket.artifacts.arn}/tmp/*" in terraform
    assert "ManageLabCatalog" in terraform
    tag_statement = terraform.split('sid       = "TagGlueNetworkInterfaces"', 1)[1].split(
        "\n  statement {", 1
    )[0]
    assert 'actions   = ["ec2:CreateTags", "ec2:DeleteTags"]' in tag_statement
    assert ":network-interface/*" in tag_statement
    assert 'variable = "aws:TagKeys"' in tag_statement
    assert 'values   = ["aws-glue-service-resource"]' in tag_statement
    runtime_policy = terraform.split("ReadLabArtifactObjects", maxsplit=1)[1].split(
        "ReadLabDatabaseSecrets", maxsplit=1
    )[0]
    assert "s3:PutObject" not in runtime_policy.split("UseLabTemporaryObjects", maxsplit=1)[0]
    assert '"--additional-python-modules"' not in terraform
    assert '"--TempDir"' in terraform
    assert '"s3://${aws_s3_bucket.artifacts.id}/tmp/"' in terraform
    for output in (
        "glue_catalog_database_name",
        "postgres_glue_connection_name",
        "mongodb_glue_connection_name",
        "mongodb_glue_secret_name",
        "glue_crawler_name",
        "glue_job_name",
        "glue_artifact_prefix",
    ):
        assert f'output "{output}"' in outputs
    assert re.search(
        r"aws_glue_connection\.postgres\.physical_connection_requirements\[0\]\.subnet_id\s*==\s*"
        r"aws_glue_connection\.mongodb\.physical_connection_requirements\[0\]\.subnet_id",
        mock_tests,
    )
    assert "aws_glue_crawler.orders.schedule == null" in mock_tests
    assert 'aws_glue_job.orders_to_mongodb.default_arguments["--TempDir"]' in mock_tests


def _resource_block(terraform: str, resource_type: str, name: str) -> str:
    start = terraform.index(f'resource "{resource_type}" "{name}"')
    following = terraform.find('\nresource "', start + 1)
    return terraform[start:] if following == -1 else terraform[start:following]


def test_glue_scripts_are_bounded_redacted_and_user_run_only() -> None:
    makefile = read("Makefile")
    deploy = read("scripts/deploy-glue-code.sh")
    crawl = read("scripts/run-glue-crawler.sh")
    run = read("scripts/run-glue-job.sh")
    guard = read("scripts/lib/user-run-aws-guard.sh")

    assert "deploy: ## USER-RUN ONLY" in makefile
    assert "crawl: ## USER-RUN ONLY" in makefile
    assert "run: ## USER-RUN ONLY" in makefile
    for script, approval in (
        (deploy, "APPROVE_GLUE_DEPLOY"),
        (crawl, "APPROVE_GLUE_CRAWL"),
        (run, "APPROVE_GLUE_RUN"),
    ):
        assert "set -euo pipefail" in script
        assert "user-run-aws-guard.sh" in script
        assert f"require_user_run_aws {approval}" in script
        assert approval in makefile
        assert not re.search(r"(password|secret[_-]?value)\s*=", script, re.IGNORECASE)
    assert "AWS_PROFILE is required" in guard
    assert "AWS_REGION must be us-east-1" in guard
    assert "ambient AWS or Terraform override" in guard
    assert "sts get-caller-identity" in guard
    assert "AWS_ENDPOINT_URL" in guard
    assert "AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true" in guard
    assert "glue/artifacts" in deploy
    assert "glue_lab.zip" in deploy
    assert "CRAWLER_TIMEOUT_SECONDS" in crawl
    assert "1200" in crawl and "60" in crawl
    assert "LastCrawl.StartTime" in crawl
    assert "remaining_seconds" in crawl
    assert "get-crawler" in crawl
    assert "get-tables" in crawl
    assert "orders" in crawl and "order_items" in crawl
    assert "expected_schemas" in crawl
    assert "JOB_TIMEOUT_SECONDS" in run
    assert "3600" in run and "60" in run
    assert "EXPIRED" in run
    assert "remaining_seconds" in run
    assert "glue/artifacts/GIT_SHA" in run
    assert "get-job-run" in run
    assert "/aws-glue/jobs/error" in run
    assert "replaceDocument" not in run


def test_thin_job_uses_catalog_and_named_mongodb_connection_without_credentials() -> None:
    entrypoint = read("glue/jobs/postgres_orders_to_mongodb.py")

    assert "create_dynamic_frame.from_catalog" in entrypoint
    assert "build_order_documents" in entrypoint
    assert 'connection_type="mongodb"' in entrypoint
    assert '"connectionName"' in entrypoint
    assert '"replaceDocument": "true"' in entrypoint
    assert ".collect(" not in entrypoint
    assert "getResolvedOptions" in entrypoint
    for forbidden in ("PASSWORD", "USERNAME", "SECRET", "CONNECTION_URL"):
        assert f'"{forbidden}"' not in entrypoint
    assert "print(" not in entrypoint


def test_ci_requires_temurin_17_and_spark_tests_cannot_skip_missing_pyspark() -> None:
    workflow = read(".github/workflows/ci.yml")
    spark_tests = read("tests/unit/test_transformations.py")

    assert "actions/setup-java@v4" in workflow
    assert 'distribution: "temurin"' in workflow
    assert 'java-version: "17"' in workflow
    assert "pytest.importorskip" not in spark_tests


def test_runbook_uses_stdin_auth_and_documents_snapshot_deletion_limit() -> None:
    runbook = read("docs/runbook/04-RUN-MIGRATION.md")
    design = read("docs/project/DESIGN.md")
    roadmap = read("docs/project/ROADMAP.md")

    assert "jq -cn" in runbook
    assert "'{user:$username,pwd:$password}'" in runbook
    assert "docker exec -i" in runbook
    assert "db.auth" in runbook
    assert '--password "$MONGO_PASSWORD"' not in runbook
    assert "--eval" not in runbook
    assert "unset SECRET_JSON MONGO_USER MONGO_PASSWORD AUTH_JSON" in runbook
    for document in (runbook, design, roadmap):
        assert "unchanged-source reruns" in document
        assert "does not delete" in document
        assert "GLUE-050" in document


def test_deployment_package_imports_from_the_deployment_shaped_zip(tmp_path: Path) -> None:
    package_zip = tmp_path / "glue_lab.zip"
    with zipfile.ZipFile(package_zip, "w") as archive:
        for source in sorted((ROOT / "src/glue_lab").glob("*.py")):
            archive.write(source, f"glue_lab/{source.name}")
    imported = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str(package_zip)!r}); "
                "from glue_lab.transformations import build_order_documents; "
                "assert callable(build_order_documents)"
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr


def test_secret_runbooks_install_cleanup_before_secret_retrieval() -> None:
    database_runbook = read("docs/runbook/02-START-DATABASES.md")
    migration_runbook = read("docs/runbook/04-RUN-MIGRATION.md")

    assert "mktemp -d /tmp/glue-lab-secrets.XXXXXX" in database_runbook
    assert database_runbook.index("trap cleanup_lab_secret_files EXIT") < database_runbook.index(
        "aws secretsmanager get-secret-value"
    )
    assert "command -v jq" in migration_runbook
    assert "unset SECRET_JSON MONGO_USER MONGO_PASSWORD AUTH_JSON" in migration_runbook
    assert "/tmp/glue-lab-*.json" not in database_runbook
    assert migration_runbook.index("trap cleanup_mongo_secret_vars EXIT") < migration_runbook.index(
        'SECRET_JSON="$(aws secretsmanager'
    )


def test_glue_entrypoint_behavior_with_fake_glue_boundaries(caplog) -> None:
    events: list[object] = []

    class FakeFrame:
        def __init__(self, name: str, count: int) -> None:
            self.name = name
            self._count = count

        def cache(self):
            events.append(("cache", self.name))
            return self

        def count(self) -> int:
            events.append(("count", self.name))
            return self._count

        def unpersist(self) -> None:
            events.append(("unpersist", self.name))

    orders = FakeFrame("orders", 5)
    items = FakeFrame("items", 9)
    documents = FakeFrame("documents", 4)

    class FakeDynamicSource:
        def __init__(self, frame: FakeFrame) -> None:
            self.frame = frame

        def toDF(self) -> FakeFrame:
            return self.frame

    class FakeCatalogReader:
        def from_catalog(self, **kwargs):
            events.append(("catalog", kwargs))
            return FakeDynamicSource(orders if kwargs["table_name"] == "orders" else items)

    class FakeSink:
        def from_options(self, **kwargs) -> None:
            events.append(("sink", kwargs))

    class FakeGlueContext:
        def __init__(self, _spark_context) -> None:
            self.create_dynamic_frame = FakeCatalogReader()
            self.write_dynamic_frame = FakeSink()

        def get_logger(self):
            events.append("glue_logger")
            return logging.getLogger("glue_entrypoint_test")

    class FakeJob:
        def __init__(self, _context) -> None:
            pass

        def init(self, name, args) -> None:
            events.append(("init", name, args))

        def commit(self) -> None:
            events.append("commit")

    class FakeDynamicFrame:
        @staticmethod
        def fromDF(frame, _context, name):
            events.append(("dynamic", frame, name))
            return ("dynamic", frame)

    args = {
        "JOB_NAME": "job",
        "CATALOG_DATABASE": "catalog",
        "ORDERS_TABLE": "orders",
        "ORDER_ITEMS_TABLE": "order_items",
        "MONGODB_CONNECTION": "mongo-connection",
        "MONGODB_DATABASE": "migration_lab",
        "MONGODB_COLLECTION": "orders",
        "SNAPSHOT_MODE": "snapshot",
    }

    fake_modules = {
        "awsglue": types.ModuleType("awsglue"),
        "awsglue.context": types.ModuleType("awsglue.context"),
        "awsglue.dynamicframe": types.ModuleType("awsglue.dynamicframe"),
        "awsglue.job": types.ModuleType("awsglue.job"),
        "awsglue.utils": types.ModuleType("awsglue.utils"),
        "pyspark": types.ModuleType("pyspark"),
        "pyspark.context": types.ModuleType("pyspark.context"),
        "glue_lab": types.ModuleType("glue_lab"),
        "glue_lab.transformations": types.ModuleType("glue_lab.transformations"),
    }
    fake_modules["awsglue.context"].GlueContext = FakeGlueContext
    fake_modules["awsglue.dynamicframe"].DynamicFrame = FakeDynamicFrame
    fake_modules["awsglue.job"].Job = FakeJob
    fake_modules["awsglue.utils"].getResolvedOptions = lambda _argv, _names: args
    fake_modules["pyspark.context"].SparkContext = types.SimpleNamespace(
        getOrCreate=lambda: object()
    )

    def fake_build(actual_orders, actual_items):
        events.append(("transform", actual_orders, actual_items))
        return documents

    fake_modules["glue_lab.transformations"].build_order_documents = fake_build
    old_modules = {name: sys.modules.get(name) for name in fake_modules}
    sys.modules.update(fake_modules)
    try:
        spec = importlib.util.spec_from_file_location(
            "glue_entrypoint_under_test", ROOT / "glue/jobs/postgres_orders_to_mongodb.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with caplog.at_level(logging.INFO):
            module.main()
    finally:
        for name, old_module in old_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module

    catalog_calls = [
        event for event in events if isinstance(event, tuple) and event[0] == "catalog"
    ]
    assert [event[1]["table_name"] for event in catalog_calls] == ["orders", "order_items"]
    assert ("transform", orders, items) in events
    assert "glue_logger" in events
    sink = next(event[1] for event in events if isinstance(event, tuple) and event[0] == "sink")
    assert sink["connection_type"] == "mongodb"
    assert sink["connection_options"] == {
        "connectionName": "mongo-connection",
        "database": "migration_lab",
        "collection": "orders",
        "replaceDocument": "true",
    }
    assert events.index("commit") > next(
        index
        for index, event in enumerate(events)
        if isinstance(event, tuple) and event[0] == "sink"
    )
    log_text = caplog.text
    assert "orders_count=5" in log_text
    assert "items_count=9" in log_text
    assert "documents_count=4" in log_text
    assert "outcome=success" in log_text
    assert "duration_seconds=" in log_text
    assert "password" not in log_text.lower()


def test_governance_makes_aws_execution_exclusively_user_run() -> None:
    governed_files = [
        "AGENTS.md",
        "README.md",
        ".github/pull_request_template.md",
        "docs/project/DESIGN.md",
        "docs/project/ROADMAP.md",
        "docs/project/COLLABORATION.md",
        "docs/project/ACCEPTANCE_CRITERIA.md",
        "docs/runbook/README.md",
        "docs/runbook/03-CONFIGURE-GLUE.md",
        "docs/runbook/04-RUN-MIGRATION.md",
    ]
    combined = "\n".join(read(path) for path in governed_files)
    assert "user-run only" in combined.lower()
    assert "must never request" in combined.lower()
    assert "AWS credentials" in combined
    assert "separate issue/PR" in combined
    assert "static" in combined.lower() and "mock" in combined.lower()
    assert "No agent-run live AWS evidence is required" in combined

    roadmap = read("docs/project/ROADMAP.md")
    assert "MERGED — PENDING LIVE VALIDATION" not in roadmap
    assert "| `GLUE-020` | DONE | [#3]" in roadmap
    assert "| `GLUE-025` | DONE | [#4]" in roadmap
    assert "| `GLUE-030` | IN PROGRESS | PR #5 PLACEHOLDER |" in roadmap
    assert "| `GLUE-040` | IN PROGRESS | PR #5 PLACEHOLDER |" in roadmap
    assert "| `GLUE-050` | NOT STARTED |" in roadmap
    assert "| `GLUE-060` | NOT STARTED |" in roadmap

    acceptance = read("docs/project/ACCEPTANCE_CRITERIA.md")
    assert "User-run-only rerun behavior (optional lab evidence)" in acceptance
    assert "User-run-only destruction and cost (optional lab evidence)" in acceptance
    assert "may be recorded later as user-supplied redacted evidence" in acceptance


def test_glue_runbooks_are_complete_user_owned_operational_guides() -> None:
    for path in ("docs/runbook/03-CONFIGURE-GLUE.md", "docs/runbook/04-RUN-MIGRATION.md"):
        runbook = read(path)
        assert "Status: implementation complete" in runbook
        assert "User-run only" in runbook
        assert "template until implementation" not in runbook
        for field in (
            "**Purpose**",
            "**Run from**",
            "**Prerequisites**",
            "**Inputs**",
            "**Command**",
            "**Expected result**",
            "**Verify**",
            "**Repeat, reset, or rollback**",
            "**If it fails**",
            "**Next**",
        ):
            assert field in runbook


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def _run_script(
    repo_root: Path,
    relative_path: str,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(repo_root / relative_path)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_user_run_glue_scripts_fail_closed_and_work_with_fake_service_boundaries(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    aws_log = tmp_path / "aws.log"
    fake_aws = fake_bin / "aws"
    fake_terraform = fake_bin / "terraform"
    fake_git = fake_bin / "git"
    fake_sleep = fake_bin / "sleep"

    _write_executable(
        fake_aws,
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import zipfile

args = sys.argv[1:]
with pathlib.Path(os.environ["FAKE_AWS_LOG"]).open("a") as handle:
    handle.write(" ".join(args) + "\\n")
if "sts" in args and "get-caller-identity" in args:
    if os.environ.get("AWS_IGNORE_CONFIGURED_ENDPOINT_URLS") != "true":
        raise SystemExit("configured endpoint URLs were not disabled")
    print("test-account")
elif args[:2] == ["s3", "cp"] and args[2].startswith("s3://") and args[3] == "-":
    print(("b" if os.environ.get("FAKE_SHA_MISMATCH") == "1" else "a") * 40)
elif args[:2] == ["s3", "cp"] and args[2].endswith("glue_lab.zip"):
    names = sorted(zipfile.ZipFile(args[2]).namelist())
    pathlib.Path(os.environ["FAKE_ZIP_NAMES"]).write_text("\\n".join(names))
elif args[:2] == ["glue", "start-crawler"]:
    if os.environ.get("FAKE_CRAWLER_START_FAIL") == "1":
        raise SystemExit(7)
    marker = pathlib.Path(os.environ["FAKE_CRAWLER_GENERATION"])
    generation = int(marker.read_text()) if marker.exists() else 0
    if os.environ.get("FAKE_STALE_CRAWL") != "1":
        marker.write_text(str(generation + 1))
elif args[:3] == ["glue", "get-crawler", "--name"]:
    query = args[args.index("--query") + 1]
    marker = pathlib.Path(os.environ["FAKE_CRAWLER_GENERATION"])
    generation = int(marker.read_text()) if marker.exists() else 0
    values = {
        "Crawler.LastCrawl.Status": "SUCCEEDED",
        "Crawler.LastCrawl.StartTime": f"2026-08-14T00:00:{generation:02d}Z",
        "Crawler.State": "READY",
    }
    print(values[query])
elif args[:2] == ["glue", "get-tables"]:
    columns = {
        "orders": [
            ("order_id", "bigint"), ("customer_id", "bigint"),
            ("customer_first_name", "string"), ("customer_last_name", "string"),
            ("customer_email", "string"), ("order_status", "string"),
            ("ordered_at", "timestamp"), ("updated_at", "timestamp"),
            ("is_deleted", "boolean"),
        ],
        "order_items": [
            ("order_item_id", "bigint"), ("order_id", "bigint"),
            ("line_number", "int"), ("sku", "string"), ("quantity", "int"),
            ("unit_price", "decimal(12,2)"), ("updated_at", "timestamp"),
            ("is_deleted", "boolean"),
        ],
    }
    if os.environ.get("FAKE_BAD_SCHEMA") == "1":
        columns["orders"][0] = ("order_id", "string")
    print(json.dumps({"TableList": [
        {"Name": name, "StorageDescriptor": {"Columns": [
            {"Name": column_name, "Type": column_type}
            for column_name, column_type in values
        ]}}
        for name, values in columns.items()
    ]}))
elif args[:2] == ["glue", "start-job-run"]:
    print("run-redacted")
elif args[:2] == ["glue", "get-job-run"]:
    print(os.environ.get("FAKE_JOB_STATE", "SUCCEEDED"))
""",
    )
    _write_executable(
        fake_terraform,
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if "workspace" in args and "show" in args:
    print("default")
elif "output" in args and "-raw" in args:
    name = args[-1]
    values = {
        "artifact_bucket_name": "test-artifact-bucket",
        "aws_account_id": "test-account",
        "aws_region": "us-east-1",
        "database_private_ip": "10.0.1.10",
        "postgres_secret_name": "/aws-glue-postgres-mongodb-lab/postgres",
        "mongodb_secret_name": "/aws-glue-postgres-mongodb-lab/mongodb",
        "mongodb_glue_secret_name": "/aws-glue-postgres-mongodb-lab/mongodb-glue",
        "glue_crawler_name": "test-crawler",
        "glue_catalog_database_name": "test_catalog",
        "glue_job_name": "test-job",
    }
    print(values[name])
else:
    raise SystemExit(f"unexpected terraform arguments: {args}")
""",
    )
    _write_executable(
        fake_git,
        """#!/usr/bin/env python3
import os
import sys

args = sys.argv[1:]
if args[-2:] == ["rev-parse", "--show-toplevel"]:
    print(os.environ["FAKE_REPO_ROOT"])
elif args[-2:] == ["status", "--short"]:
    pass
elif args[-2:] == ["rev-parse", "HEAD"]:
    print("a" * 40)
else:
    raise SystemExit(f"unexpected git arguments: {args}")
""",
    )
    _write_executable(
        fake_sleep,
        """#!/usr/bin/env bash
printf '%s\n' "$1" >>"$FAKE_SLEEP_LOG"
/bin/sleep "$1"
""",
    )

    base_env = os.environ.copy()
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_ROLE_ARN",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_ENDPOINT_URL",
        "AWS_ENDPOINT_URL_GLUE",
        "AWS_IGNORE_CONFIGURED_ENDPOINT_URLS",
        "TF_WORKSPACE",
        "TF_DATA_DIR",
        "TF_CLI_ARGS",
        "TF_CLI_ARGS_plan",
    ):
        base_env.pop(name, None)
    base_env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{base_env['PATH']}",
            "AWS_PROFILE": "personal-test",
            "AWS_REGION": "us-east-1",
            "AWS_CLI": str(fake_aws),
            "TERRAFORM": str(fake_terraform),
            "FAKE_AWS_LOG": str(aws_log),
            "FAKE_REPO_ROOT": str(ROOT),
            "FAKE_ZIP_NAMES": str(tmp_path / "zip-names.txt"),
            "FAKE_CRAWLER_GENERATION": str(tmp_path / "crawler-generation"),
            "FAKE_SLEEP_LOG": str(tmp_path / "sleep.log"),
        }
    )

    rejected = _run_script(ROOT, "scripts/deploy-glue-code.sh", base_env)
    assert rejected.returncode != 0
    assert "APPROVE_GLUE_DEPLOY=1" in rejected.stderr
    assert not aws_log.exists()

    ambient = _run_script(
        ROOT,
        "scripts/deploy-glue-code.sh",
        base_env | {"APPROVE_GLUE_DEPLOY": "1", "AWS_ACCESS_KEY_ID": "forbidden"},
    )
    assert ambient.returncode != 0
    assert "ambient AWS or Terraform override" in ambient.stderr
    assert not aws_log.exists()

    endpoint_override = _run_script(
        ROOT,
        "scripts/deploy-glue-code.sh",
        base_env | {"APPROVE_GLUE_DEPLOY": "1", "AWS_ENDPOINT_URL_GLUE": "https://invalid"},
    )
    assert endpoint_override.returncode != 0
    assert "endpoint override" in endpoint_override.stderr.lower()
    assert not aws_log.exists()

    empty_endpoint_override = _run_script(
        ROOT,
        "scripts/deploy-glue-code.sh",
        base_env | {"APPROVE_GLUE_DEPLOY": "1", "AWS_ENDPOINT_URL_GLUE": ""},
    )
    assert empty_endpoint_override.returncode != 0
    assert "endpoint override" in empty_endpoint_override.stderr.lower()
    assert not aws_log.exists()

    repo_root = tmp_path / "aws-glue-postgres-mongodb-lab"
    for relative in (
        "scripts",
        "src/glue_lab",
        "glue/jobs",
        "infrastructure/terraform",
    ):
        (repo_root / relative).mkdir(parents=True, exist_ok=True)
    for relative in (
        "scripts/deploy-glue-code.sh",
        "scripts/run-glue-crawler.sh",
        "scripts/run-glue-job.sh",
        "scripts/lib/user-run-aws-guard.sh",
        "scripts/put-lab-secrets.sh",
        "glue/jobs/postgres_orders_to_mongodb.py",
        "src/glue_lab/__init__.py",
        "src/glue_lab/transformations.py",
    ):
        destination = repo_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    (repo_root / "infrastructure/terraform/terraform.tfstate").write_text("{}")

    env = base_env | {"FAKE_REPO_ROOT": str(repo_root)}
    rejected_secret_endpoint = _run_script(
        repo_root,
        "scripts/put-lab-secrets.sh",
        env
        | {
            "APPROVE_LAB_SECRETS": "1",
            "AWS_ENDPOINT_URL_SECRETSMANAGER": "https://invalid",
        },
    )
    assert rejected_secret_endpoint.returncode != 0
    assert "endpoint override" in rejected_secret_endpoint.stderr.lower()
    assert not aws_log.exists()

    secrets_stored = _run_script(
        repo_root,
        "scripts/put-lab-secrets.sh",
        env | {"APPROVE_LAB_SECRETS": "1"},
    )
    assert secrets_stored.returncode == 0, secrets_stored.stderr
    assert "No secret value was printed" in secrets_stored.stdout
    secret_writes = [
        line
        for line in aws_log.read_text().splitlines()
        if "secretsmanager put-secret-value" in line
    ]
    assert len(secret_writes) == 3
    assert {line.split("--secret-id ", 1)[1].split()[0] for line in secret_writes} == {
        "/aws-glue-postgres-mongodb-lab/postgres",
        "/aws-glue-postgres-mongodb-lab/mongodb",
        "/aws-glue-postgres-mongodb-lab/mongodb-glue",
    }
    assert all("--secret-string file://" in line for line in secret_writes)

    for relative, approval in (
        ("scripts/deploy-glue-code.sh", "APPROVE_GLUE_DEPLOY"),
        ("scripts/run-glue-crawler.sh", "APPROVE_GLUE_CRAWL"),
        ("scripts/run-glue-job.sh", "APPROVE_GLUE_RUN"),
    ):
        result = _run_script(
            repo_root,
            relative,
            env
            | {
                approval: "1",
                "CRAWLER_POLL_SECONDS": "1",
                "JOB_POLL_SECONDS": "1",
            },
        )
        assert result.returncode == 0, result.stderr
        assert "PASS" in result.stdout

    zip_names = (tmp_path / "zip-names.txt").read_text().splitlines()
    assert "glue_lab/__init__.py" in zip_names
    assert "glue_lab/transformations.py" in zip_names

    bad_schema = _run_script(
        repo_root,
        "scripts/run-glue-crawler.sh",
        env
        | {
            "APPROVE_GLUE_CRAWL": "1",
            "CRAWLER_POLL_SECONDS": "1",
            "FAKE_BAD_SCHEMA": "1",
        },
    )
    assert bad_schema.returncode != 0
    assert "expected catalog tables and schemas" in bad_schema.stderr

    failed_job = _run_script(
        repo_root,
        "scripts/run-glue-job.sh",
        env
        | {
            "APPROVE_GLUE_RUN": "1",
            "FAKE_JOB_STATE": "FAILED",
            "JOB_POLL_SECONDS": "1",
        },
    )
    assert failed_job.returncode != 0
    assert "/aws-glue/jobs/error" in failed_job.stderr
    assert "run-redacted" not in failed_job.stdout + failed_job.stderr

    expired_job = _run_script(
        repo_root,
        "scripts/run-glue-job.sh",
        env
        | {
            "APPROVE_GLUE_RUN": "1",
            "FAKE_JOB_STATE": "EXPIRED",
            "JOB_POLL_SECONDS": "1",
        },
    )
    assert expired_job.returncode != 0
    assert "EXPIRED" in expired_job.stderr

    stale_crawl = _run_script(
        repo_root,
        "scripts/run-glue-crawler.sh",
        env
        | {
            "APPROVE_GLUE_CRAWL": "1",
            "FAKE_STALE_CRAWL": "1",
            "CRAWLER_TIMEOUT_SECONDS": "2",
            "CRAWLER_POLL_SECONDS": "60",
        },
    )
    assert stale_crawl.returncode != 0
    assert "newer crawl" in stale_crawl.stderr.lower()
    crawler_sleeps = [int(value) for value in (tmp_path / "sleep.log").read_text().splitlines()]
    assert crawler_sleeps and max(crawler_sleeps) <= 2 < 60

    (tmp_path / "sleep.log").unlink()
    timed_out_job = _run_script(
        repo_root,
        "scripts/run-glue-job.sh",
        env
        | {
            "APPROVE_GLUE_RUN": "1",
            "FAKE_JOB_STATE": "RUNNING",
            "JOB_TIMEOUT_SECONDS": "2",
            "JOB_POLL_SECONDS": "60",
        },
    )
    assert timed_out_job.returncode != 0
    assert "did not finish" in timed_out_job.stderr
    job_sleeps = [int(value) for value in (tmp_path / "sleep.log").read_text().splitlines()]
    assert job_sleeps and max(job_sleeps) <= 2 < 60

    failed_start = _run_script(
        repo_root,
        "scripts/run-glue-crawler.sh",
        env | {"APPROVE_GLUE_CRAWL": "1", "FAKE_CRAWLER_START_FAIL": "1"},
    )
    assert failed_start.returncode != 0
    assert "could not be started" in failed_start.stderr

    before_bounds = aws_log.read_text().splitlines()
    for relative, approval, overrides in (
        (
            "scripts/run-glue-crawler.sh",
            "APPROVE_GLUE_CRAWL",
            {"CRAWLER_TIMEOUT_SECONDS": "1201"},
        ),
        (
            "scripts/run-glue-crawler.sh",
            "APPROVE_GLUE_CRAWL",
            {"CRAWLER_POLL_SECONDS": "61"},
        ),
        ("scripts/run-glue-job.sh", "APPROVE_GLUE_RUN", {"JOB_TIMEOUT_SECONDS": "3601"}),
        ("scripts/run-glue-job.sh", "APPROVE_GLUE_RUN", {"JOB_POLL_SECONDS": "61"}),
    ):
        bounded = _run_script(repo_root, relative, env | {approval: "1"} | overrides)
        assert bounded.returncode != 0
        assert "maximum" in bounded.stderr.lower()
    after_bounds = aws_log.read_text().splitlines()[len(before_bounds) :]
    assert all(" glue " not in f" {line} " for line in after_bounds)

    sha_mismatch = _run_script(
        repo_root,
        "scripts/run-glue-job.sh",
        env | {"APPROVE_GLUE_RUN": "1", "FAKE_SHA_MISMATCH": "1"},
    )
    assert sha_mismatch.returncode != 0
    assert "artifact revision" in sha_mismatch.stderr.lower()
    assert "a" * 40 not in sha_mismatch.stdout + sha_mismatch.stderr
    assert "b" * 40 not in sha_mismatch.stdout + sha_mismatch.stderr

    log_text = aws_log.read_text()
    assert "sts get-caller-identity" in log_text
    assert "s3 cp" in log_text
    assert "glue start-crawler" in log_text
    assert "glue start-job-run" in log_text
    assert "password" not in log_text.lower()
