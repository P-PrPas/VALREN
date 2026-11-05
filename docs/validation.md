# Validation record

## Phase 0

- Local Python 3.14: 6 unittest checks pass after two Claude Lab review rounds.
- GitHub Actions Python 3.12 and 3.14: initial foundation checks passed.
- No live integrations or containers started.

## Phase 1

- Local Python 3.14: 11 unittest checks pass.
- Public-source smoke (`radar --live --dry-run`, 6 Nov 2026 Asia/Bangkok): arXiv fetched 200, GitHub 400, Hugging Face 200 before per-source clipping; 300 unique candidates ingested into isolated memory; selection clipped to 100. All three public APIs responded successfully.
- Frontier feed list is empty by default, so frontier HTTP fetching is NOT verified live; parser has fixtures. Operator must configure primary publisher feeds before claiming four-source coverage.
- Notion payloads, timeout handling and ownership rules tested with fakes only. No credentials supplied, so live schema/permissions and multi-day pilot remain pending.
- No LLM requests, Discord messages or Telegram messages sent.
