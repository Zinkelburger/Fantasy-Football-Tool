# Archive

Superseded code kept for reference. Nothing here is wired into the live
pipeline; git history (tag `pre-reorg-2026` and earlier) is the authority
if you need to dig further back.

- `go-tool/` — the Go desktop draft tool (Charm TUI + HTTP server for the
  browser extension). Superseded by `webapp/`, which serves the same job
  as a static site. The board CSVs and player notes it read now live in
  `data/ranks/` and `data/notes/` and are still maintained — only the Go
  app itself is retired. It still builds (`cd go-tool && make build`) but
  expects `analysis/` and the CSVs alongside the binary. Its GitHub
  release workflow is preserved as `go-tool/release.workflow.yml`.
- `2024/` — the original Python draft tool. `analysis/` and `ADR.csv` are
  still read as inputs by `research/reddit-notes-study/`.
- `2025/` — snapshot of the 2025-season Go tool. `go/analysis/` and
  `go/std_with_depth.csv` are still read by `research/reddit-notes-study/`.
- `dist/` — Linux packaging scaffolding (debian/, .desktop) for the Go tool.
- `design.md`, `first-prompt` — the original design notes the project
  started from.
