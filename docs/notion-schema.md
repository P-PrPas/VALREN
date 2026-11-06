# Research Library setup

Create a dedicated database with one data source. The CLI does not create databases automatically. Record the data source ID (not database ID) in `config/settings.toml`.

Use these exact property names/types:

```text
Title                  title
Type                   select: Repo, Open model (LLM), Open model (CV), Frontier LLM, Paper
Canonical ID           rich_text
Source URL             url
Status                 select: New, Recommended, Reading, Deep-dived, Skipped
Recommended on         date
Relevance              number
Summary                rich_text
Why it matters to me   rich_text
Tags                   multi_select
Feedback               select: Liked, Disliked
My notes               rich_text
Published on           date
Discovered on          date
Verification status    select: Unverified, Source-checked, Conflicting
```

Share only this database with a new dedicated integration with Read/Insert/Update content. Use a separate Read-only integration for the single Interest Profile page. Never share their parent workspace pages. Store tokens in environment variables shown in `.env.example`; the worker does not read other agents' files or shell profiles.

Notion writes are opt-in (`radar --live --sync-notion`). Run `sync-library` to rebuild local history before recommendations. Exact canonical-ID conflicts stop the affected writes. A create request is recorded as uncertain before network I/O; if interrupted it reconciles via a query on the next run. If no matching page appears, manually verify Notion before clearing `create_uncertain:<key>` in local state. This favors avoiding duplicates over automatic blind retries.

Sources: [Create page](https://developers.notion.com/reference/post-page), [Query data source](https://developers.notion.com/reference/query-a-data-source), [Capabilities](https://developers.notion.com/reference/capabilities).
