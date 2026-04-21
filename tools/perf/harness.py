import csv
import functools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import click
import psutil
from rich import box
from rich.console import Console
from rich.table import Table


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT  = Path(__file__).resolve().parents[2]
VENV_BIN   = REPO_ROOT / ".venv" / "bin"

DEFAULT_TIMEOUT_S  = 1800   # 30 minutes per repo
DEFAULT_RULESET    = "default"
DEFAULT_MIN_LINES  = 5
DEFAULT_CLONE_BASE = "~/.config/treepeat-dev"

_USR_BIN_TIME = "/usr/bin/time"


@functools.lru_cache(maxsize=1)
def _time_wrapper_ok() -> bool:
    """Return True if /usr/bin/time supports the platform flag (-l/-v).

    Probed once per process via lru_cache.  On minimal Linux systems
    (Alpine, some containers) /usr/bin/time is busybox and does not support
    -v; on those platforms the wrapper is disabled and only the polled RSS
    is available.
    """
    flag = "-l" if sys.platform == "darwin" else "-v"
    try:
        r = subprocess.run(
            [_USR_BIN_TIME, flag, "true"],
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False

# Strip ANSI escape codes (Rich logging emits these)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\(B")

# Extensions treepeat can process
_KNOWN_EXTS: frozenset[str] = frozenset({
    ".py", ".pyw",
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx",
    ".java",
    ".rs",
    ".go",
    ".c", ".h",
    ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx",
    ".rb",
    ".cs",
    ".kt", ".kts",
    ".swift",
})

# Dirs to skip when counting source files
_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", ".pnp",
    "target", "build", "dist", ".gradle", ".maven",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".tox",
    "coverage_html_report", ".next", ".nuxt", ".cache",
    ".pio", "log", "archive",
})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PerfResult:
    name:              str
    root:              str
    languages:         list

    # Pre-run file census
    src_files:         int   = 0    # source files with known extensions
    src_lines:         int   = 0    # total source lines

    # Outcome
    timed_out:         bool  = False
    error:             str   = ""

    # Timing (seconds)
    elapsed_s:         float = 0.0

    # Memory — two independent sources
    peak_rss_mb:        float = 0.0  # from /usr/bin/time -l (authoritative on clean exit)
    peak_polled_rss_mb: float = 0.0  # max of background poller samples (only source on timeout)
    page_faults:        int   = 0    # hard page faults (I/O reads) — key swapping indicator
    swaps:              int   = 0    # actual swap-out operations

    # Stage counts (from INFO log lines on stdout)
    parse_succeeded:   int   = 0    # "Parse complete: N succeeded"
    regions_extracted: int   = 0    # "Extracted N total region(s)"
    regions_to_shingle:int   = 0    # "Shingling N region(s) across" (after min_lines filter)
    regions_shingled:  int   = 0    # "Shingling complete: N region(s)"
    signatures:        int   = 0    # "Created N signature(s)"
    groups_found:      int   = 0    # "found N similar group(s)"
    candidate_pairs:   int   = 0    # "Total candidate pairs entering verification: N"

    # Per-stage elapsed times (seconds) parsed from inline "(Xs)" suffixes
    t_parse_s:         float = 0.0  # parse stage
    t_extract_s:       float = 0.0  # region extraction
    t_shingle_s:       float = 0.0  # shingling
    t_minhash_s:       float = 0.0  # minhash
    t_lsh_s:           float = 0.0  # LSH similarity search

    # Clone count from SARIF (cross-check vs groups_found)
    sarif_clones:      int   = 0

    # RSS time series: list of [elapsed_s, rss_mb] snapshots from background poller.
    # Sampled every 15 s; runs shorter than the interval will have an empty list.
    # Each entry is a 2-element list so it round-trips cleanly through JSON.
    rss_samples:       list  = field(default_factory=list)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

@dataclass
class Defaults:
    clone_base: str = DEFAULT_CLONE_BASE


@dataclass
class RepoConfig:
    name:           str
    languages:      list        = field(default_factory=list)
    url:            str | None  = None
    ref:            str | None  = None
    path:           str | None  = None
    clone_to:       str | None  = None
    ignore_dirs:    list        = field(default_factory=list)  # dir names to skip
    extra_args:     list        = field(default_factory=list)  # passed through to treepeat detect
    enabled:        bool        = True
    notes:          str         = ""


def load_config(toml_path: Path) -> tuple[Defaults, list[RepoConfig]]:
    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)
    defaults = Defaults(**{k: v for k, v in raw.get("defaults", {}).items()
                            if k in Defaults.__dataclass_fields__})
    repos = [RepoConfig(**{k: v for k, v in r.items()
                            if k in RepoConfig.__dataclass_fields__})
             for r in raw.get("repos", [])]
    return defaults, repos


def resolve_root(repo: RepoConfig, defaults: Defaults) -> Path:
    if repo.path:
        return Path(repo.path).expanduser()
    base = Path(repo.clone_to).expanduser() if repo.clone_to \
           else Path(defaults.clone_base).expanduser() / repo.name
    return base


# ---------------------------------------------------------------------------
# File counting
# ---------------------------------------------------------------------------


def count_source_files(root: Path, ignore_dirs: list[str]) -> tuple[int, int]:
    """Return (file_count, total_lines) for source files under root.

    Skips _SKIP_DIRS, hidden dirs, and any dirs listed in ignore_dirs.
    """
    skip = _SKIP_DIRS | set(ignore_dirs)
    total_files = 0
    total_lines = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in skip and not d.startswith(".")
        ]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() not in _KNOWN_EXTS:
                continue
            total_files += 1
            try:
                text = fpath.read_bytes()
                total_lines += text.count(b"\n")
            except OSError:
                pass

    return total_files, total_lines


# ---------------------------------------------------------------------------
# Repo cloning
# ---------------------------------------------------------------------------

CLONE_TIMEOUT_S = 300  # 5 minutes per clone


def clone_repo(repo: RepoConfig, root: Path) -> bool:
    """Clone repo.url to root, checking out repo.ref.  Returns True on success."""
    if not repo.url:
        print(f"  cannot clone {repo.name}: no url in config", file=sys.stderr)
        return False

    root.parent.mkdir(parents=True, exist_ok=True)
    _emit(f"   cloning {repo.url} → {root}")

    # Decide clone strategy: --branch works for tags and branch names but not
    # bare commit SHAs.  Detect a SHA (40 hex chars) and fall back to a full
    # clone + checkout so arbitrary commits work.
    ref = repo.ref
    is_sha = ref is not None and len(ref) >= 7 and all(c in "0123456789abcdefABCDEF" for c in ref)

    try:
        if is_sha:
            # Full clone (no --depth) then checkout the commit
            subprocess.run(
                ["git", "clone", repo.url, str(root)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=CLONE_TIMEOUT_S,
            )
            subprocess.run(
                ["git", "-C", str(root), "checkout", str(ref)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=60,
            )
        else:
            subprocess.run(
                ["git", "clone", "--depth", "1",
                 *(["--branch", ref] if ref else []),
                 repo.url, str(root)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=CLONE_TIMEOUT_S,
            )
        return True
    except subprocess.TimeoutExpired:
        _emit(f"   git clone timed out after {CLONE_TIMEOUT_S}s — cleaning up {root}")
        shutil.rmtree(root, ignore_errors=True)
        return False
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
        _emit(f"   git clone failed: {err}")
        return False


# ---------------------------------------------------------------------------
# Treepeat runner
# ---------------------------------------------------------------------------

def _find_treepeat_binary() -> str | None:
    """Find treepeat binary in venv or PATH."""
    for name in ("treepeat", "treepeat.exe"):
        candidate = VENV_BIN / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("treepeat")


def _kill_proc_group(proc: subprocess.Popen) -> None:
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(pgid, signal.SIGKILL)
            proc.wait()
    except (ProcessLookupError, PermissionError):
        pass


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _parse_time_stats(stderr: str) -> dict:
    """Parse /usr/bin/time output from stderr.

    Returns dict with keys: peak_rss_mb, page_faults, swaps.

    macOS -l output (bytes for RSS):
        1234567  maximum resident set size
          12345  page reclaims
            678  page faults
              0  swaps

    Linux -v output (kbytes for RSS):
        Maximum resident set size (kbytes): 12345
        Major (requiring I/O) page faults: 678
        Swaps: 0
    """
    stats: dict = {"peak_rss_mb": 0.0, "page_faults": 0, "swaps": 0}

    if sys.platform == "darwin":
        m = re.search(r"^\s*(\d+)\s+maximum resident set size", stderr, re.MULTILINE)
        if m:
            stats["peak_rss_mb"] = int(m.group(1)) / (1024 * 1024)
        m = re.search(r"^\s*(\d+)\s+page faults", stderr, re.MULTILINE)
        if m:
            stats["page_faults"] = int(m.group(1))
        m = re.search(r"^\s*(\d+)\s+swaps", stderr, re.MULTILINE)
        if m:
            stats["swaps"] = int(m.group(1))
    else:
        m = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", stderr)
        if m:
            stats["peak_rss_mb"] = int(m.group(1)) / 1024
        m = re.search(r"Major \(requiring I/O\) page faults:\s*(\d+)", stderr)
        if m:
            stats["page_faults"] = int(m.group(1))
        m = re.search(r"Swaps:\s*(\d+)", stderr)
        if m:
            stats["swaps"] = int(m.group(1))

    return stats


def _parse_stage_counts(text: str) -> dict:
    """Extract per-stage counts and elapsed times from treepeat stdout (ANSI-stripped).

    Parses both counts ("Parse complete: N succeeded") and the inline stage
    timings treepeat emits in parentheses ("Parse complete: N succeeded (24.6s)").
    """
    clean = _strip_ansi(text)
    counts: dict = {}

    m = re.search(r"Parse complete:\s*(\d+) succeeded.*?\(([\d.]+)s\)", clean)
    if m:
        counts["parse_succeeded"] = int(m.group(1))
        counts["t_parse_s"]       = float(m.group(2))
    else:
        m = re.search(r"Parse complete:\s*(\d+) succeeded", clean)
        if m:
            counts["parse_succeeded"] = int(m.group(1))

    m = re.search(r"Extracted (\d+) total region", clean)
    if m:
        counts["regions_extracted"] = int(m.group(1))
    m = re.search(r"Extracted \d+ region\(s\) from \d+ file\(s\) \(([\d.]+)s\)", clean)
    if m:
        counts["t_extract_s"] = float(m.group(1))

    m = re.search(r"Shingling (\d+) region\(s\) across", clean)
    if m:
        counts["regions_to_shingle"] = int(m.group(1))

    m = re.search(r"Shingling complete:\s*(\d+) region.*?\(([\d.]+)s\)", clean)
    if m:
        counts["regions_shingled"] = int(m.group(1))
        counts["t_shingle_s"]      = float(m.group(2))
    else:
        m = re.search(r"Shingling complete:\s*(\d+) region", clean)
        if m:
            counts["regions_shingled"] = int(m.group(1))

    m = re.search(r"Created (\d+) signature.*?\(([\d.]+)s\)", clean)
    if m:
        counts["signatures"]  = int(m.group(1))
        counts["t_minhash_s"] = float(m.group(2))
    else:
        m = re.search(r"Created (\d+) signature", clean)
        if m:
            counts["signatures"] = int(m.group(1))

    m = re.search(r"found (\d+) similar group.*?\(([\d.]+)s\)", clean)
    if m:
        counts["groups_found"] = int(m.group(1))
        counts["t_lsh_s"]      = float(m.group(2))
    else:
        m = re.search(r"found (\d+) similar group", clean)
        if m:
            counts["groups_found"] = int(m.group(1))

    m = re.search(r"Total candidate pairs entering verification:\s*(\d+)", clean)
    if m:
        counts["candidate_pairs"] = int(m.group(1))

    return counts


def _count_sarif_clones(sarif_path: Path) -> int:
    """Count clone results in SARIF output file."""
    try:
        data = json.loads(sarif_path.read_text(encoding="utf-8"))
        total = 0
        for run in data.get("runs", []):
            total += len(run.get("results", []))
        return total
    except Exception:
        return -1


def _find_treepeat_child_pid(wrapper_pid: int) -> int | None:
    """Return the PID of the treepeat child spawned by /usr/bin/time."""
    try:
        parent = psutil.Process(wrapper_pid)
        children = parent.children()
        return children[0].pid if children else None
    except (psutil.Error, ProcessLookupError):
        return None


def _poll_rss(
    wrapper_pid: int,
    t0: float,
    stop: threading.Event,
    interval_s: float,
    samples: list,
    use_wrapper: bool,
) -> None:
    """Background thread: sample RSS every interval_s seconds.

    When /usr/bin/time wraps treepeat, wrapper_pid is /usr/bin/time's PID
    and we look for its child (the actual treepeat process).  When no wrapper
    is used (use_wrapper=False), wrapper_pid IS treepeat's PID.
    """
    target_pid: int | None = None

    def _sample(pid: int) -> bool:
        """Sample RSS for pid; return False if the process has exited."""
        try:
            rss_bytes = psutil.Process(pid).memory_info().rss
            rss_mb = rss_bytes / (1024 * 1024)
            elapsed = time.monotonic() - t0
            samples.append([elapsed, rss_mb])
            return True
        except (psutil.Error, ProcessLookupError):
            return False

    # Take an immediate sample so short runs (< interval_s) still get data.
    # Give the process a moment to start before the first read.
    stop.wait(1.0)
    if not stop.is_set():
        pid0 = (
            _find_treepeat_child_pid(wrapper_pid) if use_wrapper else wrapper_pid
        ) or wrapper_pid
        _sample(pid0)
        target_pid = pid0 if pid0 != wrapper_pid else None

    while not stop.wait(interval_s):
        if target_pid is None:
            if use_wrapper:
                target_pid = _find_treepeat_child_pid(wrapper_pid)
            else:
                target_pid = wrapper_pid

        pid = target_pid if target_pid is not None else wrapper_pid

        if not _sample(pid):
            break


def run_treepeat(
    repo: RepoConfig,
    root: Path,
    timeout_s: int,
    dry_run: bool,
    log_path: Path,
) -> PerfResult:
    """Run treepeat on a repo and return performance metrics."""
    result = PerfResult(
        name=repo.name,
        root=str(root),
        languages=list(repo.languages),
    )

    result.src_files, result.src_lines = count_source_files(root, repo.ignore_dirs)

    if dry_run:
        return result

    binary = _find_treepeat_binary()
    if binary is None:
        result.error = "treepeat binary not found"
        return result

    ignore_globs = ",".join(f"**/{d}/**" for d in repo.ignore_dirs if d)

    with tempfile.NamedTemporaryFile(suffix=".sarif", delete=False) as tmp:
        sarif_path = Path(tmp.name)

    try:
        cmd = [
            binary,
            "-l", "INFO",
            "-r", DEFAULT_RULESET,
            "detect", str(root),
            "-f", "sarif",
            "-o", str(sarif_path),
            "--min-lines", str(DEFAULT_MIN_LINES),
        ]
        if ignore_globs:
            cmd += ["--ignore", ignore_globs]
        if repo.extra_args:
            cmd += repo.extra_args

        time_flag = "-l" if sys.platform == "darwin" else "-v"
        use_wrapper = os.path.exists(_USR_BIN_TIME) and _time_wrapper_ok()
        if os.path.exists(_USR_BIN_TIME) and not use_wrapper:
            _emit(
                f"WARNING: /usr/bin/time does not support {time_flag} on this "
                f"platform — peak RSS, page-fault, and swap data will be "
                f"unavailable; polled RSS is the only memory source"
            )
        if use_wrapper:
            cmd = [_USR_BIN_TIME, time_flag] + cmd

        t0 = time.monotonic()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        rss_samples: list = []
        stop_event = threading.Event()
        poll_thread = threading.Thread(
            target=_poll_rss,
            args=(proc.pid, t0, stop_event, 15.0, rss_samples, use_wrapper),
            daemon=True,
        )
        poll_thread.start()

        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout_s)
            result.elapsed_s = time.monotonic() - t0
        except subprocess.TimeoutExpired:
            result.elapsed_s = time.monotonic() - t0
            _kill_proc_group(proc)
            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=5)
            except Exception:
                stdout_bytes = b""
                stderr_bytes = b""
            result.timed_out = True
        finally:
            stop_event.set()
            poll_thread.join(timeout=5)

        result.rss_samples = rss_samples
        if rss_samples:
            result.peak_polled_rss_mb = max(mb for _, mb in rss_samples)

        stdout_text = stdout_bytes.decode(errors="replace")
        stderr_text = stderr_bytes.decode(errors="replace")

        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n{'='*60}\n{repo.name}  ({root})\n{'='*60}\n")
            lf.write(f"cmd: {' '.join(cmd)}\n")
            lf.write(f"elapsed: {result.elapsed_s:.1f}s  timed_out: {result.timed_out}\n")
            lf.write("\n--- STDOUT ---\n")
            lf.write(stdout_text or "(empty)\n")
            lf.write("\n--- STDERR ---\n")
            lf.write(stderr_text or "(empty)\n")

        counts = _parse_stage_counts(stdout_text)
        for k, v in counts.items():
            setattr(result, k, v)

        if result.timed_out:
            pass
        elif proc.returncode != 0:
            result.error = f"exit {proc.returncode}"
            ts = _parse_time_stats(stderr_text)
            result.peak_rss_mb = ts["peak_rss_mb"]
            result.page_faults = ts["page_faults"]
            result.swaps       = ts["swaps"]
        else:
            ts = _parse_time_stats(stderr_text)
            result.peak_rss_mb  = ts["peak_rss_mb"]
            result.page_faults  = ts["page_faults"]
            result.swaps        = ts["swaps"]
            result.sarif_clones = _count_sarif_clones(sarif_path)

    finally:
        sarif_path.unlink(missing_ok=True)

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_CSV_FIELDS = [
    "name", "languages",
    "src_files", "src_lines",
    "parse_succeeded", "regions_extracted", "regions_to_shingle", "regions_shingled",
    "signatures", "groups_found", "candidate_pairs", "sarif_clones",
    "t_parse_s", "t_extract_s", "t_shingle_s", "t_minhash_s", "t_lsh_s",
    "elapsed_s", "peak_rss_mb", "peak_polled_rss_mb", "rss_sample_count", "page_faults", "swaps",
    "timed_out", "error",
]


def write_csv(results: list[PerfResult], csv_path: Path) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row["languages"] = "+".join(r.languages)
            row["rss_sample_count"] = len(r.rss_samples)
            writer.writerow({k: row[k] for k in _CSV_FIELDS})


def write_json(results: list[PerfResult], json_path: Path) -> None:
    data = [asdict(r) for r in results]
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _status_symbol(result: PerfResult) -> str:
    if result.timed_out:
        return "⏱"
    if result.error:
        return "✗"
    return "✓"


def _mem_mb(result: PerfResult) -> float:
    return max(result.peak_rss_mb, result.peak_polled_rss_mb)


def _format_mem(result: PerfResult) -> str:
    mem_mb = _mem_mb(result)
    return f"{mem_mb:.0f}M" if mem_mb else "0M"


def _build_result_table(include_repo: bool) -> tuple[Table, Console]:
    console = Console()
    table = Table(box=box.SIMPLE_HEAVY, expand=False)
    table.add_column("", justify="center", width=1, no_wrap=True)
    if include_repo:
        table.add_column("Repo", no_wrap=True)
    table.add_column("File", justify="right", no_wrap=True)
    table.add_column("Shngs", justify="right", no_wrap=True)
    table.add_column("Pair", justify="right", no_wrap=True)
    table.add_column("Clon", justify="right", no_wrap=True)
    table.add_column("Shng", justify="right", no_wrap=True)
    table.add_column("Hash", justify="right", no_wrap=True)
    table.add_column("LSH", justify="right", no_wrap=True)
    table.add_column("Mem", justify="right", no_wrap=True)
    return table, console


def _add_result_row(table: Table, result: PerfResult, include_repo: bool) -> None:
    row = [_status_symbol(result)]
    if include_repo:
        row.append(result.name)
    row.extend([
        str(result.src_files),
        str(result.regions_shingled),
        str(result.candidate_pairs),
        str(result.sarif_clones),
        f"{result.t_shingle_s:.1f}",
        f"{result.t_minhash_s:.1f}",
        f"{result.t_lsh_s:.1f}",
        _format_mem(result),
    ])
    table.add_row(*row)


def print_repo_summary(result: PerfResult) -> None:
    """Print a compact per-repo summary table."""
    table, console = _build_result_table(include_repo=False)
    _add_result_row(table, result, include_repo=False)
    print()
    console.print(table)
    print()


def print_summary(results: list[PerfResult]) -> None:
    """Print a human-readable end-of-run summary table."""
    table, console = _build_result_table(include_repo=True)

    for r in results:
        _add_result_row(table, r, include_repo=True)

    print()
    console.print(table)
    print()


def _emit(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{ts}  {msg}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _default_config_path() -> Path:
    return Path(__file__).with_name("perf_repos.toml")


@click.command()
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    default=_default_config_path,
    show_default=True,
    help="TOML config file.",
)
@click.option(
    "--repo",
    help="Run only this repo (by name).",
)
@click.option(
    "--timeout",
    type=click.IntRange(1),
    default=DEFAULT_TIMEOUT_S,
    show_default=True,
    help="Per-repo timeout in seconds.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Count files only, do not run treepeat.",
)
@click.option(
    "--clone",
    "clone_missing",
    is_flag=True,
    help="Clone missing repos before running (requires url in config).",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=REPO_ROOT / "tools" / "perf" / "output",
    show_default=True,
    help="Directory for output files.",
)
def main(
    config: Path,
    repo: str | None,
    timeout: int,
    dry_run: bool,
    clone_missing: bool,
    output_dir: Path,
) -> None:
    """Treepeat performance characterization harness."""
    if not config.exists():
        raise click.ClickException(
            f"Config not found: {config}\nCreate a perf_repos.toml in tools/perf/ or pass --config."
        )

    defaults, all_repos = load_config(config)
    repos = [r for r in all_repos if r.enabled]

    if repo:
        repos = [r for r in repos if r.name == repo]
        if not repos:
            raise click.ClickException(f"No enabled repo named '{repo}' in {config}")

    if not repos:
        raise click.ClickException("No enabled repos in config.")

    # Verify roots exist; optionally clone missing ones
    ready = []
    for r in repos:
        root = resolve_root(r, defaults)
        if not root.exists():
            if clone_missing:
                ok = clone_repo(r, root)
                if not ok:
                    _emit(f"SKIP {r.name}: clone failed")
                    continue
            else:
                _emit(f"SKIP {r.name}: root not found: {root}")
                _emit("       → clone it manually or re-run with --clone")
                continue
        ready.append((r, root))

    if not ready:
        raise click.ClickException("No repo roots found. Use --clone to clone missing repos.")

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = output_dir / f"run_{ts}.log"
    csv_path  = output_dir / f"run_{ts}.csv"
    json_path = output_dir / f"run_{ts}.json"

    binary = _find_treepeat_binary()
    mode = "(dry-run)" if dry_run else f"timeout={timeout}s ruleset={DEFAULT_RULESET}"
    _emit(f"treepeat_perf  {ts}  {len(ready)} repo(s)  {mode}")
    if binary and not dry_run:
        _emit(f"treepeat: {binary}")
    _emit(f"log: {log_path}")
    print()

    results: list[PerfResult] = []

    for repo, root in ready:
        lang_str = "+".join(repo.languages) if repo.languages else "?"
        _emit(f"── {repo.name} ({lang_str})  src_root={root.name}")

        result = run_treepeat(
            repo=repo,
            root=root,
            timeout_s=timeout,
            dry_run=dry_run,
            log_path=log_path,
        )
        results.append(result)

        if dry_run:
            _emit(f"   {result.src_files} src files  {result.src_lines:,} lines")
            print_repo_summary(result)
        elif result.error:
            _emit(f"   ✗ error: {result.error}  ({result.elapsed_s:.1f}s)")
            print_repo_summary(result)
        elif result.timed_out:
            rss_note = (f"  rss_peak={result.peak_polled_rss_mb:.0f}MiB"
                        f" ({len(result.rss_samples)} samples)"
                        if result.rss_samples else "")
            _emit(f"   ✗ TIMEOUT after {result.elapsed_s:.0f}s{rss_note}")
            print_repo_summary(result)
        else:
            rss    = (f"  rss={result.peak_rss_mb:.0f}MiB(time)/{result.peak_polled_rss_mb:.0f}MiB(poll)"
                      if result.peak_rss_mb or result.peak_polled_rss_mb else "")
            faults = f"  pfaults={result.page_faults:,}" if result.page_faults else ""
            swaps  = f"  swaps={result.swaps}" if result.swaps else ""
            _emit(
                f"   ✓ {result.elapsed_s:.1f}s{rss}{faults}{swaps}"
                f"  files={result.src_files}"
                f"  parsed={result.parse_succeeded}"
                f"  regions={result.regions_extracted}"
                f"  shingled={result.regions_shingled}"
                f"  pairs={result.candidate_pairs}"
                f"  clones={result.sarif_clones}"
            )
            print_repo_summary(result)

    if len(results) > 1:
        print_summary(results)

    if not dry_run:
        write_csv(results, csv_path)
        write_json(results, json_path)
        _emit(f"CSV:  {csv_path}")
        _emit(f"JSON: {json_path}")
    _emit(f"Log:  {log_path}")


if __name__ == "__main__":
    main()
