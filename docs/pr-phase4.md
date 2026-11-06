## Summary

Complete the user feedback loop and require human approval before other agents can start paid research.

```text
Notion / authenticated Telegram feedback → bounded taste → relevance adjustment
signed agent request → read-only search OR pending → human approval → one fixed Tutor job
local scheduler → daily claim → resumable stages → bounded retries
```

## Evidence

- **Before:** no taste learning, buttons, signed request inbox or daily service.
  **After:** 58 offline tests pass, including preference effects, chat-bound buttons, HMAC tampering/late replay/operation scope, exact-target expiring approval, scheduler partial progression/stale leases/busy retry, and fresh digest priority. Compose config validates. Both Claude review rounds and final fixes are recorded in reviews.md.
- Container smoke job is added to CI. No live bots, integration credentials or persistent containers were started.

## Merge Danger

**Door:** two-way

**Blast Radius:** integrations

Stacked on PR #4. Agent transport wiring and Malren's read-only credential must be provisioned separately; no root files or other agent settings are modified. agent_net defaults off; approved research still obeys budget and weekly caps. Scheduler/poller/notices profiles are opt-in; outbound-only notices can coexist with Hermes polling. Gateway approval is an authenticated user command with exact ID/target confirmation. See agent-requests.md and deployment gates in validation.md.
