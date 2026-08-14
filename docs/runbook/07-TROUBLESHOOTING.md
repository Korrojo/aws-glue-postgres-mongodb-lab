# 07 — Troubleshooting

Owner: each component task adds its failures; `GLUE-060` performs final review  
Status: grows with observed implementation failures

Use one section per observed or strongly expected failure.

## Required failure-entry format

### Symptom or exact error fragment

- **Step:** numbered runbook step where it occurs
- **Likely cause:** one or two specific causes
- **Diagnose:** exact read-only command
- **Expected diagnostic result:** what confirms the cause
- **Fix:** smallest corrective command or configuration change
- **Retry:** exact command that repeats the failed step
- **Reset impact:** whether data or infrastructure is changed

## Required coverage before release

- wrong AWS profile or Region;
- missing AWS permission or `iam:PassRole`;
- Terraform provider/init failure;
- EC2 SSM status not online;
- Git clone/pull failure;
- Docker image pull or container health failure;
- PostgreSQL authentication or JDBC failure;
- MongoDB authentication or connection failure;
- Glue ENI/security-group failure;
- Secrets Manager access failure;
- crawler failure or wrong catalog tables;
- Glue job failure and CloudWatch log location;
- MongoDB duplicate/replacement behavior mismatch;
- reconciliation mismatch;
- Terraform destroy blocked by remaining S3 objects or dependencies.

Do not solve these failures by adding production infrastructure or public database access.

