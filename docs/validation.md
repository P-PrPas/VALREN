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

- 39 local unittest checks after final review fixes; Compose syntax validates.
- Hermes plugin import/registration verified by Plugin Doctor in the installed pinned image, without network/secrets and with checkout mounted read-only. This is a disposable validation container, not an active agent.
- Host memory measured: 1,151 MiB available, swap 4,076/4,095 MiB used. Persistent deployment is deferred until capacity is addressed.

## Phase 4 / final local verification

- 53 unittest checks pass under local Python 3.14; final checks include scheduler partial/fatal separation, stale leases, busy retry, delivery counters, exact-target single-use approvals, late authenticated status replay, request rate limit, foreign-chat callbacks, envelope size/FIFO rejection and fresh digest priority over ready/uncertain backlog.
- `docker compose config --quiet` passes. All five PR heads passed GitHub Actions Python 3.12/3.14 checks. Implementation head `4d72fda` also passed the worker-container build/doctor smoke; the final documentation-only record may produce a newer head. Check the live PR checks for that exact head.
- Latest post-fix public-source dry-run on 6 Nov: arXiv fetched 100; GitHub fetched 96; 185 unique candidates preserved; Hugging Face returned RemoteError so the run was explicitly partial (exit 10). No Notion writes, LLM calls or messages. HF had succeeded in the earlier smoke; current reachability/quota still needs operator validation. No frontier feed is configured, so only its parser is fixture-verified.
- All changes and runtime smoke artifacts are confined to valren. No persistent agent, bot, local scheduler or T3 recurring task was started. Remote main is initialization only; five stacked PRs await owner review.

## Remaining live acceptance gates

- Create/share the isolated Library and flat Interest Profile with separate writer/reader integrations; run live schema/permission tests, including an explicitly unshared fixture page.
- Confirm real interests, model/provider compatibility/prices, monthly budget, bot/chat identity and official frontier feeds. Current defaults intentionally reject paid use.
- Exercise Notion create/update/reconcile, Discord receipt/429/uncertain behavior and authorized/unauthorized Telegram identities with real dedicated credentials. Verify pinned Hermes runtime tool inventory and adapter-to-command identity before gateway use.
- Provision the chosen agent request transport, individual signing keys and Malren's own read-only Library credential; existing agents/root config are untouched. Hermes-mode proactive request notices need a trusted gateway adapter or manual /valren_requests.
- Complete at least a three-day Radar pilot, seven-day digest quality pilot, real peak-memory measurements and an operator backup/restore drill including worker, scheduler and .hermes state. The existing central restic job has not been changed because it is outside valren.
