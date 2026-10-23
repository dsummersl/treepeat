import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil


def create_corpus(root: Path) -> int:
    """Repeat synthetic PHP functions across directories, including dependencies."""
    randomizer = random.Random(8241)
    for family in range(32):
        statements = [f"    $value += {randomizer.randrange(100000000)};" for _ in range(128)]
        source = "<?php\nfunction calculate() {\n    $value = 0;\n" + "\n".join(statements) + "\n}\n"
        for copy in range(16):
            directory = root / ("vendor" if copy % 2 else "app") / str(copy)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"family_{family}.php").write_text(source)
    return 512


def stop_process(process: subprocess.Popen) -> None:
    for child in psutil.Process(process.pid).children(recursive=True):
        child.kill()
    process.kill()
    process.wait()


def measure(command: list[str], log: Path) -> dict:
    started = time.monotonic()
    peak = 0
    with log.open("w") as output:
        process = subprocess.Popen(command, stdout=output, stderr=output)
        while process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                rss = sum(p.memory_info().rss for p in [parent, *parent.children(recursive=True)])
                peak = max(peak, rss)
            except psutil.Error:
                pass
            if time.monotonic() - started > 120 or peak > 512 * 1024 ** 2:
                stop_process(process)
                raise RuntimeError("Synthetic scan exceeded 120 seconds or 512 MiB combined RSS")
            time.sleep(0.05)
    if process.returncode:
        raise RuntimeError(log.read_text())
    return {"elapsed_seconds": round(time.monotonic() - started, 2), "peak_rss_mib": round(peak / 1024 ** 2, 2)}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="treepeat-ci-") as temporary:
        root = Path(temporary)
        count = create_corpus(root / "source")
        report = root / "report.sarif"
        command = [
            sys.executable, "-c", "from treepeat.cli import main; main()", "detect", str(root / "source"),
            "--similarity", "90", "--min-lines", "15", "--ignore-files", "", "--format", "sarif",
            "--output", str(report),
        ]
        metrics = measure(command, root / "scan.log")
        run = json.loads(report.read_text())["runs"][0]
        assert run["properties"]["filesDiscovered"] == count
        assert run["properties"]["filesParsed"] == count
        assert run["properties"]["processingComplete"]
        assert len(run["results"]) == 32
        assert all(result["properties"]["groupSize"] == 16 for result in run["results"])
        print(json.dumps({**metrics, "files": count, "groups": len(run["results"])}))


if __name__ == "__main__":
    main()
