# Performance Characterization Harness

`tools/perf/harness.py` measures treepeat's time and memory usage across a
range of real-world repos to establish the file-count / SLOC / clone-density
vs. time+memory curve.  The primary goal is to guide optimization work and
validate (or refute) the swapping hypothesis: that memory pressure becomes
acute around 2,000–3,000 source files on a 32 GB machine.

## Quick start

```bash
# 1. Set up the project environment
make setup

# 2. Clone repos and run (first time only)
uv run python tools/perf/harness.py --clone

# 3. Run again without cloning
uv run python tools/perf/harness.py

# 4. Single repo
uv run python tools/perf/harness.py --repo requests

# 5. File census only — no treepeat invocation
uv run python tools/perf/harness.py --dry-run
```

Output lands in `tools/perf/output/` (gitignored):

| File | Contents |
|------|----------|
| `run_<ts>.log` | Full stdout+stderr for each repo |
| `run_<ts>.csv` | One row per repo — import into a spreadsheet for curve fitting |
| `run_<ts>.json` | Structured results, machine-readable, includes RSS time series |

## Config file

The default config is `tools/perf/perf_repos.toml`.  Pass `--config PATH` to
use a different file.

```toml
[defaults]
clone_base = "~/.config/treepeat-dev"   # where repos are cloned

[[repos]]
name       = "requests"
url        = "https://github.com/psf/requests"
ref        = "v2.33.1"
languages  = ["python"]                 # informational
notes      = "Small baseline"

[[repos]]
name        = "django"
url         = "https://github.com/django/django"
ref         = "4.2"
languages   = ["python"]
ignore_dirs = ["docs"]       # excluded from file census and treepeat scan
extra_args  = []             # passed directly to `treepeat detect`
enabled     = true           # set false to skip without deleting
```

All repos listed in the config are run.  Set `enabled = false` to skip one
without removing it.

### Field reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Short identifier; used as the clone directory name |
| `url` | for `--clone` | Git URL |
| `ref` | no | Branch, tag, or commit to check out |
| `path` | no | Absolute local path — skips `clone_base` entirely |
| `clone_to` | no | Per-repo clone path override |
| `languages` | no | Informational label(s), e.g. `["python"]` |
| `ignore_dirs` | no | Directory names excluded from file census and converted to `--ignore **/dir/**` for treepeat |
| `extra_args` | no | Extra flags passed directly to `treepeat detect` |
| `enabled` | no | Default `true`; set `false` to skip |
| `notes` | no | Free-form description |

## CLI flags

```
--config PATH      TOML config file (default: tools/perf/perf_repos.toml)
--repo NAME        Run only this repo
--timeout S        Per-repo timeout in seconds (default: 1800)
--dry-run          Count source files only; do not invoke treepeat
--clone            Clone repos that are missing from disk
--output-dir DIR   Output directory (default: tools/perf/output/)
```

## Console summary

The live per-repo summary is intentionally compact.

- `Shngs` = `regions_shingled`
- `Shng` = `t_shingle_s`
- `Mem` = `max(peak_rss_mb, peak_polled_rss_mb)`

For full per-stage timings and raw metrics, use the CSV/JSON outputs.

## What is measured

**File census**: source file count and total line count, excluding standard
skip dirs (`node_modules`, `__pycache__`, `build`, etc.) and any dirs listed
in `ignore_dirs`.

**Timing**: wall-clock elapsed time for the full treepeat invocation.

**Memory** (two independent sources):
- `/usr/bin/time -l` (macOS) / `-v` (Linux): authoritative peak RSS on clean
  exit, plus hard page faults and swap counts — the key swapping indicators.
- Background RSS poller: samples the treepeat process via `psutil` every 15 s.
  This is the only memory source when treepeat times out.

**Per-stage counts** (parsed from INFO log output):
`parse_succeeded`, `regions_extracted`, `regions_to_shingle`,
`regions_shingled`, `signatures`, `groups_found`, `candidate_pairs`.
`candidate_pairs` is the total number of region pairs entering ordered-similarity verification
(sum of C(|group|, 2) over all candidate groups); it distinguishes
false-candidate-explosion (large value relative to N) from raw-scale slowness.

**Per-stage elapsed times** (when treepeat emits inline `(Xs)` suffixes):
`t_parse_s`, `t_extract_s`, `t_shingle_s`, `t_minhash_s`, `t_lsh_s`.

**Clone count**: total SARIF results (cross-check against `groups_found`).

## Platform notes

| Platform | `/usr/bin/time` flag | `ps` poller | Status |
|----------|----------------------|-------------|--------|
| macOS | `-l` (bytes RSS) | yes | fully supported |
| Linux (glibc, standard distros) | `-v` (kbytes RSS) | yes | fully supported |
| Linux (Alpine / busybox containers) | not supported | yes | harness warns and falls back to polled RSS only; page-fault and swap counts unavailable |
| Windows | not present | no | not supported (contributions welcome!) |

The harness probes `/usr/bin/time <flag> true` once (via `lru_cache`) before
the first run and logs a warning if the flag is unsupported.  All other
metrics (stage counts, elapsed time, SARIF clone count, polled RSS) are
unaffected.

## Invocation

The harness is a standalone script, not a pytest suite. Invoke it directly:

```bash
make setup
uv run python tools/perf/harness.py --clone
```

## Wishlist

Features that would improve instrumentation without requiring external tools:

1. **Per-stage elapsed time to stderr** — emit `Stage N/5: <name> [elapsed Xs]`
   so stage wall time is available regardless of output format.
2. **`--verbose` with `-f sarif`** — verbose metrics currently only appear in
   console mode; they should also go to stderr in sarif mode.
3. **Peak RSS self-reporting** — emit `resource.getrusage(RUSAGE_SELF).ru_maxrss`
   to stderr at pipeline end to avoid the `/usr/bin/time` wrapper requirement.
4. **Structured PERF log line** — emit a single `WARNING`-level line with all
   stage counts so it is always visible without `--verbose`.
5. **`--min-regions`** — skip repos with fewer than N extracted regions for
   quick early-exit on effectively-empty scans.
