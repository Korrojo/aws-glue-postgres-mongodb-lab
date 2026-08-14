# 06 — Destroy the Lab

Owner: `GLUE-060`  
Status: template until implementation

## Required completed sections

1. State clearly that stopping EC2 is not complete cleanup.
2. Confirm the AWS account, Region, Terraform directory, and project tags.
3. Run the pre-destroy resource and cost inventory.
4. Handle only the known lab artifacts that would block Terraform destroy.
5. Review and run Terraform destroy.
6. Verify EC2, Glue job/crawler/connections, S3 bucket, secrets, endpoints, and networking are removed.
7. Remove the optional GitHub deploy key if it was created.
8. Verify no known project-tagged billable resources remain.
9. Explain how to recover from a partial destroy without broad deletion commands.
10. State what local files may remain and which sensitive temporary files must not remain.

Every destructive command must resolve an exact lab target before execution.

