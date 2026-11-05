# Review ledger

Review quota: at most two Claude Lab / Opus 5.5 / medium review threads per PR. PRs remain open for the owner; never auto-merge.

## PR #1 — Phase 0

- Round 1 thread: `mcp:c7d8204c-b564-4e9e-a6f6-5d2ce43a9a05`.
- Addressed: URL canonicalization rejects credentials and normalizes hosts/ports; documented primary URL IDs rather than fabricated release IDs. Namespaced many-to-many aliases retain reused-name history. `VALREN_HOME`/working directory works for non-editable installs; CI now installs normally. Nested field types, config keys, Notion IDs, candidate source/type/host and HF traversal validated. SQLite backup closes destination; schema version recorded. Errors from SQLite are sanitized; config/fixture paths confined. Counts report clipping and duplicates, with fixture-only preview labeled explicitly. TOML/unittest plan drift corrected.
- Remaining low-risk follow-up: CI action SHA pinning and avoiding duplicate push/PR CI triggers. Dry-run intentionally previews supplied fixtures, not production state, in this phase.
- Added regression checks for alias reuse, backup/restore and invalid metadata/config.
- Round 2 (final): `mcp:c8e3bf52-be41-4dcf-b304-6e7e45c3df31`; medium findings confirmed fixed. Addressed remaining input type/RecursionError sanitization, falsy Notion ID validation, database version downgrade and stale README/evidence. Query-parameter policy and legacy payload quarantine are deferred to their source/sync implementations. No third review requested. PR stays open for owner.
