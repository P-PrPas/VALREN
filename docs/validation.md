# Validation record

## Phase 0

- Local Python 3.14: 6 unittest checks pass after two Claude Lab review rounds.
- GitHub Actions Python 3.12 and 3.14: initial foundation checks passed.
- No live integrations or containers started.

## Phase 1

- Local Python 3.14: 17 unittest checks pass after final review fixes.
- Pre-review-fix public-source smoke (`radar --live --dry-run`, 6 Nov 2026 Asia/Bangkok): arXiv fetched 200, GitHub 400, Hugging Face 200 before per-source clipping; 300 unique candidates ingested into isolated memory; selection clipped to 100. All three public APIs responded successfully. These counts precede the fair topic/task quotas added after review, and are not current coverage measurements.
- Frontier feed list is empty by default, so frontier HTTP fetching is NOT verified live; parser has fixtures. Operator must configure primary publisher feeds before claiming four-source coverage.
- Notion payloads, timeout handling and ownership rules tested with fakes only. No credentials supplied, so live schema/permissions and multi-day pilot remain pending.
- No LLM requests, Discord messages or Telegram messages sent.

## Phase 2

- 29 local unittest checks after two Claude Lab rounds. Paid-response caching, partial failures, uncertain sends, budget reservation and stale-job recovery tested with fakes.
- Offline digest preview renders successfully. No paid/live integration credentials supplied.

## Phase 3

- 34 local unittest checks; Compose syntax validates.
- Hermes plugin import/registration verified by Plugin Doctor in the installed pinned image, without network/secrets and with checkout mounted read-only. This is a disposable validation container, not an active agent.
- Host memory measured: 1,151 MiB available, swap 4,076/4,095 MiB used. Persistent deployment is deferred until capacity is addressed.
