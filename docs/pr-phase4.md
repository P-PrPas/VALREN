## Summary

Complete the user feedback loop and require human approval before other agents can start paid research.

```text
Notion / authenticated Telegram feedback → bounded taste → relevance adjustment
signed agent request → read-only search OR pending → human approval → one fixed Tutor job
local scheduler → daily claim → resumable stages → bounded retries
```

## Evidence

- **Before:** no taste learning, buttons, signed request inbox or daily service.
  **After:** 43 offline tests pass, including preference effects, chat-bound feedback buttons, HMAC tampering/replay/operation scope, expiring single-use approval, and scheduler day deduplication. Compose config validates; `schedule --once` waits outside its configured window without network or paid calls.
- Container smoke job is added to CI. No live bots, integration credentials or persistent containers were started.

## Merge Danger

**Door:** two-way

**Blast Radius:** integrations

Stacked on PR #4. Agent transport wiring and Malren's read-only credential must be provisioned separately; no root files or other agent settings are modified. agent_net defaults off; approved research still obeys budget and weekly caps. Scheduler/poller profiles are opt-in. See agent-requests.md and deployment gates in validation.md.
