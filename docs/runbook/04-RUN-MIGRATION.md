# 04 — Run the Snapshot Migration

Owner: `GLUE-040`  
Status: template until implementation

## Required completed sections

1. Explain the source-to-target mapping with one concrete order example.
2. Confirm database health, catalog tables, Glue artifact, and empty/known target state.
3. Start the Glue job with exact non-secret parameters.
4. Wait for completion with an explicit timeout.
5. Describe expected job status and stable CloudWatch log messages.
6. Verify MongoDB document count and one representative nested document.
7. Explain which transformations to observe: normalization, embedding, item order, decimals, and soft-delete exclusion.
8. State what is safe to rerun and what target behavior is expected.
9. Provide focused recovery for job failure, missing catalog table, serialization/type, and MongoDB write failures.
10. Link to `05-VALIDATE-AND-RERUN.md`.

Do not introduce CDC or streaming in this runbook.

