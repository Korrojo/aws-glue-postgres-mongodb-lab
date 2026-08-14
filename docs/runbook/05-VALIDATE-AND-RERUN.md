# 05 — Reconcile and Test Rerun Behavior

Owner: `GLUE-050`  
Status: template until implementation

## Required completed sections

1. Explain why order count alone is insufficient.
2. Run reconciliation with exact source and target identifiers but no credentials on the command line.
3. Show expected pass output for order count, item count, keys, totals, ordering, normalization, and deletions.
4. Inspect the redacted machine-readable result.
5. Run the identical Glue job a second time.
6. Verify target document count did not increase.
7. Apply the controlled source update defined by the test fixture.
8. Rerun and verify the corresponding MongoDB document changed correctly.
9. Demonstrate one intentional mismatch and the expected nonzero validation result, then reset it.
10. Provide focused recovery for count, total, ordering, stale-target, and duplicate-key mismatches.
11. Link to `06-DESTROY.md`.

