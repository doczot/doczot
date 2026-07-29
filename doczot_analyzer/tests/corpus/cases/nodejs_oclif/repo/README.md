# sitecheck

A static site link checker.

## Commands

### `sitecheck crawl`

Crawls a site and records every link found.

Flags:

- `--depth` — how many levels deep to follow links.
- `--concurrency` — number of parallel requests.

### `sitecheck report`

Renders a report from the most recent crawl.

Flags:

- `--format` — output format: `text`, `json` or `html`.
