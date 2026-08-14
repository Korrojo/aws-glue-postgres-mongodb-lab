# 02 — Start and Verify the Databases

Owners: `GLUE-010`, finalized by `GLUE-020`  
Status: template until implementation

## Required completed sections

1. Explain where Docker runs in the core lab: EC2, not the Mac.
2. Confirm EC2 SSM status and repository clone.
3. Pull the reviewed `main` branch and record the Git SHA.
4. Retrieve secrets without displaying them.
5. Start PostgreSQL and MongoDB with Docker Compose.
6. Show the expected container health output.
7. Verify PostgreSQL schema, source row counts, and foreign-key integrity.
8. Verify MongoDB authentication, database, and initially empty target collection.
9. Explain safe restart, reseed, and volume-reset behavior.
10. Provide focused recovery for image-pull, port, permission, health-check, and initialization failures.
11. Link to `03-CONFIGURE-GLUE.md`.

The optional Mac Docker smoke test belongs in a clearly labeled appendix.

