# Review ledger

Review quota: at most two Claude Lab / Opus 5.5 / medium review threads per PR. PRs remain open for the owner; never auto-merge.

## PR #1 — Phase 0

- Round 1 thread: `mcp:c7d8204c-b564-4e9e-a6f6-5d2ce43a9a05`.
- Addressed: URL canonicalization rejects credentials and normalizes hosts/ports; documented primary URL IDs rather than fabricated release IDs. Namespaced many-to-many aliases retain reused-name history. `VALREN_HOME`/working directory works for non-editable installs; CI now installs normally. Nested field types, config keys, Notion IDs, candidate source/type/host and HF traversal validated. SQLite backup closes destination; schema version recorded. Errors from SQLite are sanitized; config/fixture paths confined. Counts report clipping and duplicates, with fixture-only preview labeled explicitly. TOML/unittest plan drift corrected.
- Follow-up completed: CI actions pinned to resolved commit SHAs; branch pushes run through PR events only, with main push checks retained. Frontier URLs strip known tracking parameters and reject all other query parameters before storage. Dry-run intentionally previews supplied fixtures, not production state, in this phase.
- Added regression checks for alias reuse, backup/restore and invalid metadata/config.
- Round 2 (final): `mcp:c8e3bf52-be41-4dcf-b304-6e7e45c3df31`; medium findings confirmed fixed. Addressed remaining input type/RecursionError sanitization, falsy Notion ID validation, database version downgrade and stale README/evidence. Query-parameter policy and legacy payload quarantine are deferred to their source/sync implementations. No third review requested. PR stays open for owner.

## Persistent reviewer

User requested reuse on 6 Nov 2026. All remaining reviews use thread `mcp:83fe4a3e-d0a6-48d3-9418-ec8d66b1d184` with Claude Lab / Opus 5.5 / medium. Do not create further reviewer threads. Each PR still has at most two rounds.

## PR #2 — Phase 1

- Round 1: same persistent thread. Fixed definite Notion rejection leaving uncertain flags; paced Notion calls and stop on auth/quota failures. Store fetched candidates before sync. Quarantine invalid/duplicate Library rows and block affected keys only. Isolate malformed source records/feeds. Divide GitHub quotas across topics and both newly-created/recently-active searches; divide HF tasks and request cardData with license fallback. Legacy single-name HF IDs accepted safely.
- Added wall-clock HTTP deadlines including DNS/header/body and a ten-minute collection deadline (main POSIX thread required). Reject non-UTF-8 XML. Backup requires a new path and excludes WAL/SHM/lock files. CLI boundary sanitizes unexpected exceptions. Added regression checks for rate-limit recovery, source records/licenses, retry/redirect, lock contention and retaining fetched data on Notion outage.
- Live smoke is recorded in validation.md; phase 1 stores metadata/New rows. Thai summaries and managed provenance blocks arrive in phases 2/3.
- Round 2 (final): all round-1 issues confirmed fixed. Cleared stale per-key conflict flags after complete sync; added a regression test. Labeled pre-fix smoke counts explicitly. Replaced the collection alarm with a shared network deadline to avoid losing batches at a nested timer restore boundary. No more PR2 reviews; left open for owner.

## PR #3 — Phase 2

- Round 1 (persistent thread): fixed paid-work loss on rank/summary failures. LLM calls are fingerprinted and durably claimed before network; successful raw responses are cached even when malformed, while ambiguous calls are held rather than re-billed. Definite rejection releases budget. Ranking preserves valid earlier batches on exhaustion and skips malformed batches. Summaries fail once per daily entry and do not block other entries. Resume unfinished digest work across midnight.
- LLM wall timeout is 300 s, independently of public fetch limits. Tags sanitized/deduplicated, generated links removed from display text, metadata observations not misrepresented as source quotations. Managed provenance documents reconcile before append and preserve user content. Delivery sends at most one digest per local day, holds ambiguous sends, expires ready messages older than yesterday; explicit resolution resets attempts.
- Added regression checks for paid response caching, released reservations, partial budget ranking, summary isolation/tag normalization and successful remote receipts. No live paid calls made.
- Round 2 (final): all round-1 findings confirmed fixed. Addressed two regressions: isolate and report Notion failures per entry so an operator gate cannot pin future digests; resumed paid work keeps its job identity but uses today's delivery/recommendation date and occupies today's single digest slot. Added stale-job regression. Health counts held LLM calls. Paid response cache remains unpruned to preserve idempotency; it caches decoded HTTP JSON before parsing model content, while non-JSON HTTP responses are held as uncertain rather than cached. No third review.
## Owner-requested follow-ups (after review quota)

- PR1: action SHA pinning, duplicate CI and Frontier query policy closed; known trackers removed, unknown/functional/credential query parameters rejected pending publisher-specific policy.
- PR2: UTF8 encoding alias accepted; incomplete/failed GitHub queries preserve returned/other results and report partial health. HF task outages are isolated too. Live HF failure reproduced as HTTP 200 with a 2,090,958-byte image-classification response exceeding the 2 MB transport cap. Removing `full` (including `full=false`, which still expands results on this endpoint) removes unneeded file listings: cardData-only response is 33,686 bytes/50 records with license tags retained. No transport size increase. Official OpenAI RSS configured and fetched live (831,593 bytes, 1,366 parsed entries before cap); feed coverage is publisher news, not a verified-model-release classifier.

- PR3: settled raw LLM bodies have 30-day retention, permanent no-rebilling tombstones, legacy grace and uncertain-call preservation. Regression verifies pruning never triggers a second paid request or changes settled spend.
