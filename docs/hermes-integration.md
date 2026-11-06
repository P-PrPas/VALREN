# Hermes / Tutor integration

The installed homelab image digest was inspected without reading any agent's mounted files/secrets:

```text
nousresearch/hermes-agent@sha256:d4da4a40cd7a28aba983775d9fd31d94cbf153eeb0cb9e844d6d0f612b7c24db
Python 3.13.5; default entrypoint /opt/hermes/docker/entrypoint-dispatch.sh
```

An isolated container with no network, no secrets, a read-only checkout and 256 MiB RAM successfully ran `hermes plugins doctor /work/hermes/valren_plugin`: manifest parsing, import and runtime registration passed. The initial warning about provides_tools was corrected in the manifest. This verifies the plugin interface, not Telegram authentication or production gateway readiness.

Choose ONE owner for the dedicated Telegram bot:

- Worker mode: invoke `telegram-poll` periodically; `/tutor <canonical-key-or-arxiv-url>` goes through strict user/chat allowlists, shared budget/weekly cap and the same Notion persistence path.
- Hermes gateway mode: enable only the VARLEN plugin and the minimum conversation surface in VARLEN's own profile. `/valren_tutor <target>` is a user slash command authenticated using task-local gateway session context, then calls a fixed-argv worker subprocess. The model tool can only search cached research with a read-only database connection. Do not run worker polling on this token at the same time.

No model-callable paid tool exists. Do not enable terminal, filesystem, arbitrary web-fetch, other integrations, broad MCP servers or other agents' profiles for VARLEN. Verify the actual enabled tool inventory before running the gateway; persona text alone is not a sandbox. Apply persona.md only after choosing a persona. Hermes' own conversational model billing is outside the worker's usage ledger, so give its provider account a separate hard spending limit and avoid autonomous host LLM tasks.

Compose mounts the tracked restricted `hermes/config.yaml` read-only and loads a separate `.env.hermes` (template supplied), excluding Discord and agent_net credentials. Run `scripts/check-hermes.sh` for the reproducible isolated contract check. It loads the real pinned runtime/config, verifies exactly `valren_library_search` in both CLI/Telegram model inventories, and dispatches slash commands through the real gateway dispatcher with synthetic authorized/unauthorized identities and a stubbed worker subprocess. This caught and fixed three integration issues: plugin enablement uses `plugins.enabled`, command names must be hyphenated for Telegram normalization, and handlers receive only raw args with identity bound in session ContextVars. The plugin reads the pinned ContextVars directly, without environment fallback; changing the image requires rerunning this contract check. Live Telegram adapter dispatch with real accounts remains to be verified before paid deployment. This is an explicit deployment gate; missing/mismatched identity fails closed.

Configure `[telegram] user_ids=[YOUR_NUMERIC_ID]` and `chat_ids=[YOUR_NUMERIC_CHAT_ID]`, a dedicated bot token and Library credentials. These arrays must be non-empty for polling. Missing task-local identity fails closed in the Hermes command, including spoofed HERMES_SESSION environment values. The CLI `tutor` is a trusted local operator action; do not expose it as an unrestricted shell tool to another agent.

Optional `[tutor_llm]` accepts the same explicit fields as `[llm]`, sharing the same monthly budget. If absent it uses the explicitly selected Radar model. The worker reserves one new lesson job per ISO week, retrying the same job without additional automatic paid calls. Partial HTML reading is capped at six chunks/24,000 characters and disclosed; unavailable HTML falls back honestly to the abstract. No PDF parser or repo code execution is included.

Source chunks/profile are snapshotted on the first attempt of an item/week so retries cannot change the job identity. Invalid chunks are skipped and disclosed; a terminal invalid lesson releases the weekly slot. `tutor --retry-invalid TARGET` or `/tutor_retry TARGET` explicitly permits at most one fresh paid attempt for that invalid job; normal retry never purchases the same invalid output again. Metadata-only items are refused until real primary text exists. Long-poll timeout is shorter than its socket and wall deadlines.

The lesson is saved to marked Notion paragraphs before Status becomes Deep-dived. A failed or partial append is held for inspection. Existing user notes, feedback and other blocks are preserved.

## Deployment gate

On 6 Nov 2026 the host had 6,816 MiB RAM, approximately 1,151 MiB available, and 4,076/4,095 MiB swap used. No persistent container was started. Free up memory or establish measured headroom before enabling another Hermes gateway. Compose is local and isolated; it does not modify the root Hermes Compose or backup job.

Create `data/` and `.hermes/` under valren and ensure UID 1000 can write only those directories before starting. `docker compose run --rm worker doctor` validates the worker. The optional `hermes` profile preserves the image's default entrypoint and requires the image's normal gateway setup in its OWN HERMES_HOME. Validate Compose and permissions first; do not assume default empty home is a configured bot.

Sources: [Hermes native plugins](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins), [Telegram Bot API](https://core.telegram.org/bots/api).
