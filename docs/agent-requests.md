# Feedback and agent requests

## Feedback

The Library's Feedback property stays user-owned: Notion edits are imported on sync. Automated summary writes still cannot modify it. Explicit local `feedback KEY Liked|Disliked` and authenticated Telegram `/like KEY`, `/dislike KEY`, or `/feedback KEY` are user operations that write only the selected Feedback field after validating Library membership.

`/feedback KEY` supplies inline buttons. Their short random tokens map to one item/chat, expire after seven days and still require the callback sender AND chat to be allowlisted. Arbitrary callback data cannot select a different item. Taste is derived without an LLM from liked/disliked tags/task/topics, held in a bounded 1,800-character block. A matching preference changes relevance by at most one point; it never blacklists an entire field after one dislike. The Hermes search tool returns this small taste context alongside existing Library results. Content knowledge remains in Notion.

## Signed request protocol

agent_net is OFF by default. Set `[agent_net] enabled=true` and `allowed_agents=["Malren"]` only after establishing an authenticated transport. The worker requires `VALREN_AGENT_NET_KEYS_JSON`, a private JSON map of agent name to a distinct signing key of at least 32 characters. Share each sender's own key only; never the worker's whole environment or another agent's key. Use the private secret-entry facility/environment on your deployment platform, not chat or a committed file.

This repository supplies the receiving policy/CLI, not an undocumented native Hermes broker API. Existing root agent networking is not modified. To connect a transport, deliver one JSON envelope inside `valren/` and invoke `agent-request PATH` through a trusted worker process. Do not expose the trusted operator CLI, worker DB, `approve-request`, or `run-approved` as arbitrary agent tools. Malren can separately get its own read-only Notion integration for the Library; this task does not change Malren's configuration.

The envelope has EXACTLY these fields:

```json
{
  "version": 1,
  "agent": "Malren",
  "request_id": "UNIQUE-REQUEST-ID-16-80-CHARS",
  "nonce": "UNIQUE-NONCE-16-80-CHARS",
  "issued_at": "2026-11-06T01:00:00+00:00",
  "operation": "research",
  "target": "arxiv:2401.12345",
  "signature": "LOWERCASE-HEX-HMAC-SHA256"
}
```

Compute signature over every field EXCEPT signature using UTF-8 `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, with HMAC-SHA256 and the sender's dedicated key. Timestamp must be within five minutes of worker time. Request IDs/nonces accept ASCII letters/digits/hyphens, length 16–80; nonce is unique per agent. The same request ID/body returns the same saved response; changing it is rejected. Rate limit is 20 new requests/hour/agent. There is no operation for file writes, configuration, arbitrary status updates or user approvals.

- `search`: target is a short Library query; returns cached results without LLM or Library writes.
- `research`: target is a canonical item ID; queues a request valid for 24 hours. MVP supports existing source items and new arXiv papers, not free-form web research or arbitrary URLs. No LLM starts on receipt.

Review requests with `requests`. A trusted human runs `approve-request ID`, then `run-approved ID`, or uses `/approve ID` in the allowlisted Telegram bot (which approves and executes that fixed request). Approval is bound to stored target/request ID, valid for 15 minutes and consumed BEFORE execution. Agents cannot place an approval in an envelope. Failure requires fresh human approval; process death in executing is held for operator inspection. Normal monthly budget and Tutor weekly limits still apply. Inspect target/agent in `requests` before approving.

## Scheduler and bot service

`schedule` is a local process, not a T3 persistent scheduled task. It checks once per minute, runs from 08:00 in configured timezone and stays quiet after 23:00. Each day is durably claimed, stages are recorded, and failures get at most three attempts spaced at least one hour apart. A process death while running is held rather than blindly starting a second job. Inspect `schedule:<date>` state and health before resetting it manually.

Default scheduling only fetches public metadata. Paid scheduling requires `--enable-paid --sync-notion`, confirmed interests and a positive budget. Sending additionally requires `--enable-delivery`. Example after live gates:

```bash
PYTHONPATH=src python3 -m valren.cli schedule --sync-notion --enable-paid --enable-delivery
PYTHONPATH=src python3 -m valren.cli telegram-serve
```

Compose has opt-in `automation` and `telegram` profiles. Do not enable `telegram` and a Hermes gateway using the same bot token together. No service was started by implementation. `telegram-serve` periodically runs bounded polling cycles and releases the worker lock between cycles. Scheduler and poller use the same per-database file lock, so busy work cannot be overwritten by another cycle.
