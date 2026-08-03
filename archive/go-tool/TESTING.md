# Testing

The Go app uses the standard `testing` package. No mocking frameworks — tests
write real files into `t.TempDir()` and read them back.

## Running

```bash
make test           # go test -v ./...
make test-verbose   # adds -race
make test-coverage  # writes coverage.out + coverage.html
make check          # fmt + vet + test, run this before committing
make watch          # re-run tests on save (requires `entr`)
```

Plain `go test ./...` works too. The tests themselves take ~1.3s; it's the
cold build that's slow, because the UI tests link Fyne — over 7 minutes on a
Linux dev box with an empty build cache. Warm runs are near-instant, so don't
kill the first one thinking it hung.

## What's covered

71 test functions across 8 files:

| File | Covers |
| --- | --- |
| `loader_test.go` | `DataLoader`: name cleaning (Jr./Sr./II/III/IV/V suffixes), CSV discovery, note-file matching, status file loading |
| `players_test.go` | CSV parsing, rank sorting, non-numeric ranks, truncated-note extraction |
| `http_server_test.go` | The `:8000` endpoint the Chrome extension POSTs to: valid/invalid methods, malformed JSON, empty bodies, CORS preflight, full channels |
| `settings_test.go` | `.env` parsing: comments, blank values, booleans, whitespace, stray `=` |
| `ui_test.go` | `FantasyUI`: update channel, LLM rate limiting, refresh, concurrent access, shutdown |
| `platform_rank_test.go` | STD / 0.5 PPR / PPR rank columns and per-platform filenames |
| `integration_test.go` | Real project CSVs against platform switching, format detection |
| `final_verification_test.go` | End-to-end platform switching, rank variation sanity check |

Deliberately not covered: OpenAI/Ollama network calls, Fyne widget rendering,
`main()` wiring.

## Coverage

Run `make test-coverage` and open `coverage.html`. Coverage concentrates in the
data layer (loader, players, settings, http_server); UI and LLM files pull the
overall number down and that's expected. `coverage.out`/`coverage.html` are
gitignored.

## Adding tests

1. Put file-system tests in `t.TempDir()` so they clean themselves up.
2. Table-driven subtests (`t.Run`) for input variations — see `TestCleanName`.
3. Cover the error path, not just the happy path. Missing files should yield
   graceful defaults rather than panics; that's what most of `loader_test.go`
   checks.
4. Mark helpers with `t.Helper()`.
