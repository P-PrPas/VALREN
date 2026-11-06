## Summary

Teach bounded research lessons and persist them before marking Deep-dived; add authenticated Telegram and Hermes entrypoints.

```text
authorized user command → existing item / arXiv paper
  → bounded source chunks → cached notes → structured Thai lesson
  → managed Notion document → Deep-dived → reply
```

## Evidence

- **Before:** no Tutor, Telegram command or Hermes adapter.
  **After:** 34 unittest checks cover authorization, honest abstract fallback, paid-work reuse after persistence failure, deferred/uncertain Telegram replies and plugin tool boundaries. `docker compose config --quiet` passes.
- Isolated, network-disabled, read-only container using the installed Hermes image digest passed Plugin Doctor manifest/import/registration. No real LLM, bot or Library credentials used; live gateway authentication remains an operator gate.

## Merge Danger

**Door:** two-way

**Blast Radius:** integrations

Stacked on PR #3. Choose either worker Telegram polling or Hermes gateway for the dedicated bot. Only cached Library search is exposed as a model tool; paid Tutor is an authenticated user command or trusted local CLI. Optional Tutor model shares monthly budget; one new lesson job/week. Compose is prepared but no persistent container is started: measured host swap is almost full. See hermes-integration.md.
