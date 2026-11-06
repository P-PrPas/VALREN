# Validation record

## Phase 0

- Local Python 3.14: 6 unittest checks pass after two Claude Lab review rounds.
- GitHub Actions Python 3.12 and 3.14: initial foundation checks passed.
- No live integrations or containers started.

## Phase 1

- Local Python 3.14: 17 unittest checks pass after final review fixes.
- Pre-review-fix public-source smoke (`radar --live --dry-run`, 6 Nov 2026 Asia/Bangkok): arXiv fetched 200, GitHub 400, Hugging Face 200 before per-source clipping; 300 unique candidates ingested into isolated memory; selection clipped to 100. All three public APIs responded successfully. These counts precede the fair topic/task quotas added after review, and are not current coverage measurements.
- At this phase Frontier feeds were empty; the owner-requested follow-up below configures and verifies an official feed.
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
- Earlier post-review public-source dry-run on 6 Nov: arXiv fetched 100; GitHub fetched 96; 185 unique candidates preserved; Hugging Face returned RemoteError so the run was explicitly partial (exit 10). No Notion writes, LLM calls or messages. HF had succeeded in the earlier smoke; current reachability/quota still needs operator validation. No frontier feed is configured, so only its parser is fixture-verified.
- All changes and runtime smoke artifacts are confined to valren. No persistent agent, bot, local scheduler or T3 recurring task was started. Remote main is initialization only; five stacked PRs await owner review.

## Owner-requested follow-up verification

- Local suite: **58 tests pass** (foundation URL query policy, UTF8 alias, partial source query preservation, cache tombstones, outbound-only notices/revoked chats added). No new Claude round: the two-review quota remains respected.
- Public dry-run after fixes: **all four sources OK**, arXiv 100, GitHub 96, Hugging Face 100, official OpenAI RSS 1,366 before the Frontier cap of 100; **385 unique candidates** after per-source caps/deduplication, pending selection capped at 100. No Notion writes, paid calls or messages. OpenAI feed covers publisher news; it does not prove model-release classification or other publishers' coverage.
- HF failure diagnosis: `full=true` response for 50 image-classification models was 2,090,958 bytes (over the 2 MB limit); `full=false` still expands on this API. Omitting `full` while retaining `cardData=true` yielded 33,686 bytes/50 records and retained license metadata. The transport bound is unchanged.
- `scripts/check-hermes.sh`: real pinned Hermes config/discovery/model schemas expose exactly `valren_library_search` for CLI and Telegram. The actual gateway dispatcher resolves underscored Telegram commands; synthetic authorized identity reaches a stubbed worker, unauthorized user/chat and environment spoof are rejected. Exact-target approval dispatch calls only fixed approve/run argv and does not execute on rejection. No external Telegram adapter or provider call is involved.
- Signed-file transport exercised through actual CLI subprocesses and a disposable local ledger: valid envelope queues pending, exact replay is idempotent, tampered signature/wrong-target approval rejected, no paid work starts. Test credentials were synthetic and discarded with the temporary directory. Native Malren wiring remains external.
- Compose configuration, compileall and diff whitespace checks pass. All artifacts remain inside valren; no persistent services are running. Check PR CI for the latest follow-up heads, as earlier successful checks covered previous heads.

## Remaining live acceptance gates

- Create/share the isolated Library and flat Interest Profile with separate writer/reader integrations; run live schema/permission tests, including an explicitly unshared fixture page.
- Confirm real interests, model/provider compatibility/prices, monthly budget, bot/chat identity and any additional official Frontier publishers. Current defaults intentionally reject paid use.
- Exercise Notion create/update/reconcile, Discord receipt/429/uncertain behavior and authorized/unauthorized Telegram identities with real dedicated credentials. Pinned runtime inventory and synthetic dispatch now pass; real Telegram adapter/account authorization must still be checked.
- Connect Malren to the supported signed-file ingress (or provision a native broker bridge), provide per-agent signing keys and Malren's own read-only Library credential; existing agents/root config are untouched. Gateway notices/approval now have tested code paths but require the dedicated live bot/allowlists.
- Complete at least a three-day Radar pilot, seven-day digest quality pilot, real peak-memory measurements and an operator backup/restore drill including worker, scheduler and .hermes state. The existing central restic job has not been changed because it is outside valren.
