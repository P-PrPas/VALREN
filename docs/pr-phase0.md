## Summary

Bootstrap an isolated research worker that validates settings and deduplicates fixture candidates without credentials.

```text
CLI → validated TOML → canonical candidates → SQLite
```

## Evidence

- **Before:** repository had no executable worker or tests.
  **After:** `PYTHONPATH=src python3 -m unittest discover -v` passes 6 tests covering version IDs, reused rename aliases, backup/restore, configuration boundaries, preserved user state and side-effect-free dry-run. `doctor` reports offline readiness, not live readiness.

## Merge Danger

**Door:** two-way

**Blast Radius:** isolated

No live services or containers started. Integration credentials and homelab RAM are not verified. This is phase 0; subsequent PRs stack on this branch. Runtime configuration uses TOML to avoid a YAML dependency.
