# Owner review / merge guide

All five PRs remain open; none was merged automatically. Each branch contains the previous phase, while its PR targets that previous branch so the review diff stays focused.

1. [PR #1 — foundation](https://github.com/P-PrPas/VALREN/pull/1), base `main`.
2. [PR #2 — Radar/Notion](https://github.com/P-PrPas/VALREN/pull/2), base `phase/0-foundation`.
3. [PR #3 — LLM/digest](https://github.com/P-PrPas/VALREN/pull/3), base `phase/1-radar`.
4. [PR #4 — Tutor/Telegram/Hermes](https://github.com/P-PrPas/VALREN/pull/4), base `phase/2-digest`.
5. [PR #5 — feedback/requests/scheduler](https://github.com/P-PrPas/VALREN/pull/5), base `phase/3-tutor`.

Review bottom to top. To merge while preserving this stack's ancestry, use merge commits (the repository allows them). After each parent merges, retarget the next PR to `main`, check its diff and checks, then merge it. Squashing a parent requires rebasing dependent branches before retargeting, otherwise parent changes can reappear in the child diff. Branch deletion on merge is currently disabled.

The local checkout is on `phase/4-feedback`, containing the complete implementation. `main` intentionally has only the initialization commit until owner review. There is no existing code history to overwrite in the previously empty remote.

Review quota is two rounds per PR. The persistent reviewer from PR #2 onward is [Claude Lab reviewer](t3-thread://v1/mcp:83fe4a3e-d0a6-48d3-9418-ec8d66b1d184). Final response/fix notes are in reviews.md. CI checks run offline/unit tests and a network-disabled worker-container doctor; they are not live Notion/Telegram/LLM acceptance tests.
