"""Compare two perf-harness runs and print a before/after markdown table.

Usage:
    uv run python tools/perf/compare.py BEFORE AFTER

BEFORE and AFTER are each a ``run_<ts>.json`` file written by harness.py, or a
directory holding one or more of them (all runs found are merged by repo name).
"""

import json
from pathlib import Path

import click


def _load(path: Path) -> dict[str, dict]:
    files = sorted(path.rglob("run_*.json")) if path.is_dir() else [path]
    if not files:
        raise click.ClickException(f"No run_*.json files found in {path}")
    results: dict[str, dict] = {}
    for f in files:
        for row in json.loads(f.read_text(encoding="utf-8")):
            results[row["name"]] = row
    return results


def _mem_mb(row: dict) -> float:
    return max(row["peak_rss_mb"], row["peak_polled_rss_mb"])


def _cpu_s(row: dict) -> float:
    return row["cpu_user_s"] + row["cpu_sys_s"]


def _delta(before: float, after: float) -> str:
    if not before:
        return "n/a"
    return f"{(after - before) / before * 100:+.1f}%"


def _row(name: str, before: dict, after: dict) -> str:
    cells = [name]
    for label, fn in (("wall", lambda r: r["elapsed_s"]), ("cpu", _cpu_s), ("mem", _mem_mb)):
        b, a = fn(before), fn(after)
        unit = "MiB" if label == "mem" else "s"
        cells += [f"{b:,.1f} {unit}", f"{a:,.1f} {unit}", _delta(b, a)]
    cells += [str(before["sarif_clones"]), str(after["sarif_clones"])]
    return "| " + " | ".join(cells) + " |"


@click.command()
@click.argument("before", type=click.Path(exists=True, path_type=Path))
@click.argument("after", type=click.Path(exists=True, path_type=Path))
def main(before: Path, after: Path) -> None:
    b_runs, a_runs = _load(before), _load(after)
    names = [n for n in b_runs if n in a_runs]
    if not names:
        raise click.ClickException("BEFORE and AFTER have no repos in common")

    click.echo(
        "| Repo | Wall before | Wall after | Δ | CPU before | CPU after | Δ "
        "| Peak RSS before | Peak RSS after | Δ | Clones before | Clones after |"
    )
    click.echo("|" + "---|" * 12)
    for name in names:
        click.echo(_row(name, b_runs[name], a_runs[name]))


if __name__ == "__main__":
    main()
