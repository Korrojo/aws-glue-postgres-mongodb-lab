# Ordered Lab Runbooks

The root README introduces the lab. These files are the executable lab manual.

Run the primary path in order:

| Order | Runbook | Outcome |
|---|---|---|
| 0 | `00-PREREQUISITES.md` | Mac, GitHub, AWS profile, Region, and required tools are ready |
| 1 | `01-DEPLOY-INFRASTRUCTURE.md` | Disposable VPC, EC2, S3, IAM, secrets, and Glue resources exist |
| 2 | `02-START-DATABASES.md` | PostgreSQL and MongoDB containers are healthy and seeded on EC2 |
| 3 | `03-CONFIGURE-GLUE.md` | Connections work and the crawler creates the intended catalog tables |
| 4 | `04-RUN-MIGRATION.md` | Glue creates the transformed MongoDB order documents |
| 5 | `05-VALIDATE-AND-RERUN.md` | Reconciliation and the second-run test pass |
| 6 | `06-DESTROY.md` | All billable lab resources are removed |

Use `07-TROUBLESHOOTING.md` only when a numbered step links to it or its focused recovery does not resolve the problem.

Optional paths must be clearly separated:

- local Docker Compose smoke testing on the Mac;
- generating a GitHub deploy key and pushing a feature branch from EC2.

Neither optional path is required to complete the core Glue lab.

## Rule for implementation PRs

These files begin as controlled templates. The task that implements a component must replace every implementation marker in the corresponding runbook with observed commands and results. A task cannot be marked `DONE` while its runbook contains missing commands, unverified output, or undocumented reset behavior.

