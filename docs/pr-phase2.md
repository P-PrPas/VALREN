## Summary

Add opt-in, budgeted Thai ranking/summaries and recoverable Discord digests.

```text
sync history → rank in batches → summarize selected items with source quotes
  → Notion Recommended → durable daily outbox → explicit Discord delivery
```

## Evidence

- **Before:** Radar stored metadata as New; no paid filtering or digest existed.
  **After:** unittest suite exercises budget reservation/settlement, paid timeout without retry, rejected fabricated evidence, daily reuse, quiet hours, uncertain-send hold and bounded digest rendering. `preview-digest tests/fixtures/digest.json` renders without secrets or paid calls.
- No real LLM/Notion/Discord credentials used. Pricing and model remain unset; paid execution fails closed by default.

## Merge Danger

**Door:** two-way

**Blast Radius:** integrations

Stacked on PR #2. Live commands can incur API cost or write/send to configured services only after explicit operator setup. Budget depends on verified provider prices and tokenizer limits; unknown usage remains reserved. Ambiguous webhook delivery is held for reconciliation, not claimed exactly-once. Verification remains Unverified pending scientific review. See operations.md.
