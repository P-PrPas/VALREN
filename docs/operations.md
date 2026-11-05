# Runbook

Run from this checkout or set `VALREN_HOME` to its absolute path. Linux/POSIX main-thread execution is required for `flock` and wall-clock network deadlines. Python 3.12+ is supported. The default configuration has no budget, unconfirmed interests, no frontier feeds and no live destination IDs.

## Local verification

```bash
PYTHONPATH=src python3 -m unittest discover -v
PYTHONPATH=src python3 -m valren.cli doctor
PYTHONPATH=src python3 -m valren.cli radar --dry-run --fixture tests/fixtures/candidates.json
PYTHONPATH=src python3 -m valren.cli preview-digest tests/fixtures/digest.json
```

Dry-run uses only an isolated database, never writes Notion/sends messages/calls LLM. `--live --dry-run` may fetch public sources. Offline tests use no credentials. `doctor` validates config only; it is not a live integration certificate.

## Live research pipeline (after configuration)

```bash
PYTHONPATH=src python3 -m valren.cli radar --live --sync-notion
PYTHONPATH=src python3 -m valren.cli recommend
# Explicit external sending:
PYTHONPATH=src python3 -m valren.cli retry-deliveries
PYTHONPATH=src python3 -m valren.cli health
```

Provide dedicated secrets only through process environment or a private `.env` consumed by Compose (`.env` is NOT automatically loaded by the Python CLI). Follow notion-schema.md. Set the real interests and `confirmed=true`. If `notion_profile_page_id` is set, recommendation reads that flat page with the separate reader token in addition to the local profile.

LLM configuration is deliberately absent from the default. Add `[llm]` with:

```toml
endpoint = "https://YOUR_PUBLIC_PROVIDER/v1/chat/completions"
model = "YOUR_EXPLICIT_MODEL_ID"
input_per_million = 0.0    # Replace with verified positive USD prices for this model.
output_per_million = 0.0   # Zero/unset means paid calls are rejected.
reserve_input_tokens = 24000
max_output_tokens = 3000
```

Set the top-level monthly_budget_usd before calling. Use a Chat Completions compatible provider/model that supports `max_completion_tokens`, JSON object responses and `usage.prompt_tokens/completion_tokens`. No tools are exposed. Provider-specific extra fees are not modeled; choose a text-only model and set a provider-side spending limit as a second bound. The conservative input reserve uses UTF-8 bytes + framing, rejects oversized input, and is not a guarantee for arbitrary third-party tokenizers. Validate model pricing/tokenization in the live pilot. Usage exceeding the configured bound blocks later calls pending operator reconciliation.

Rank in batches of five (at most candidate_limit); summarize only selected items. A saved daily job reuses generated summaries across failures. Evidence quotes must be exact substrings of fetched source text; this verifies citation shape, not scientific truth or entailment, so Verification stays Unverified. Abstract/metadata coverage must be disclosed. No automatic benchmark reproduction.

Each paid request is fingerprinted and durably claimed before network I/O. The raw response is cached before parsing; identical malformed output is never purchased again automatically. Ambiguous/inflight requests remain held for operator reconciliation. A definite rejection releases its reservation. Ranking keeps partial results when budget is exhausted; malformed summaries are skipped once rather than blocking the whole digest. Unfinished daily work is resumed across midnight. Metadata-only observations do not use fabricated source quotes.

Here, cached raw response means decoded HTTP JSON before model-content parsing. Non-JSON HTTP responses remain uncertain and are not automatically repurchased. Cache pruning is intentionally manual until retention can preserve idempotency tombstones. Resumed work consumes today's digest slot/date; per-item Notion failures are recorded and omitted so they cannot pin all future runs.

Discord sends at most one digest per local day. Ready digests older than yesterday expire; an ambiguous send occupies its daily slot until reconciled. Source URLs are the only displayed links. Managed provenance is appended as marked paragraphs; partial/uncertain appends require inspection rather than overwriting user notes.

## Recovery

- `sync-library`: rebuild Library history before paid ranking. Bad/duplicate rows are listed in health, quarantined by key and do not destroy fetched candidates. Correct or remove those rows then sync again.
- Pending Notion creation: query-based reconciliation runs before creating again. A definite rejection clears the uncertain flag; an ambiguous timeout/process crash holds it. If no page exists, inspect Notion manually before clearing the matching `create_uncertain:<key>` state with SQLite. Always take a backup first.
- Discord outbox: `ready` can be retried; `uncertain` requires checking the channel. Never retry uncertain sends blindly. After verifying, use `resolve-delivery ID --state sent --receipt MESSAGE_ID`, or `--state ready` only when definitely absent. This does not send immediately. `failed` and exhausted attempts require operator diagnosis.
- A paid request with unknown usage retains its reservation, including timeouts. Inspect provider billing and usage rows before reconciliation; do not delete the database to reset a budget. `budget_blocked` is a manual reconciliation gate.
- `backup data/backups/UNIQUE.sqlite3` creates a consistent SQLite backup into a new file. Include backups, `.hermes`, configuration and separately managed credentials in your existing protected backup process. Do not copy a live SQLite file without WAL consistency. Verify restore in a separate database under valren and run health/sync without sending. Pending/uncertain deliveries need reconciliation before resuming.

All CLI errors emit only an error type and run ID, never response bodies or secrets. Check `health` for source failures, conflicts, outbox and usage. Do not paste secret-bearing endpoint URLs into logs or tickets.

API contract source: [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create). Model selection and prices remain explicit deployment choices.
