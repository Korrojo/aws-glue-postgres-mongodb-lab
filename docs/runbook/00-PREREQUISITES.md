# 00 — Prerequisites

Owner: `GLUE-020`  
Status: template until implementation

This runbook must prepare a clean Mac Mini without assuming prior AWS Glue or Terraform setup.

## Required completed sections

1. Confirm macOS architecture and terminal shell.
2. Install and verify Git.
3. Authenticate GitHub from the Mac for normal clone/push work.
4. Install and verify AWS CLI v2.
5. Create/select the personal AWS profile.
6. Set and verify `us-east-1`.
7. Run `aws sts get-caller-identity` and explain how to detect accidental work credentials.
8. Install and verify Terraform.
9. Install and verify Make or the selected command wrapper.
10. Install Python/Java only when required by actual local tests.
11. Explain that Docker Desktop is optional unless the user chooses the local container smoke test.
12. Clone the repository and run `make doctor`.
13. State required AWS service permissions without constructing an enterprise IAM onboarding system.
14. State expected time, likely session cost, and the mandatory destroy step.

Every section must follow `docs/project/DOCUMENTATION_STANDARD.md`.

