## Summary

Radar now discovers public research and synchronizes a dedicated Notion Library without an LLM.

```text
arXiv / GitHub / HF / configured official feeds
  → bounded HTTPS → canonical candidates → SQLite → opt-in Notion New pages
```

## Evidence

- **Before:** Radar accepted only local fixtures.
  **After:** `PYTHONPATH=src python3 -m unittest discover -v` passes 11 tests, including XML rejection, source outage isolation, private-IP blocking, feed link filtering, repeated ingest and uncertain Notion creation reconciliation.
- Live public-source smoke result is recorded separately in validation notes. No Notion credentials were supplied; API payload tests do not establish live integration readiness.

## Merge Danger

**Door:** two-way

**Blast Radius:** isolated

Stacked on PR #1 (`phase/0-foundation`). Notion writes require explicit `--sync-notion`; dry-run uses an isolated in-memory store. Sources are bounded discovery, not exhaustive Trending coverage. Configure official frontier feeds before frontier discovery is active. Continuous multi-day validation remains an operator gate.
