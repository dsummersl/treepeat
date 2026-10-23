# Running large scans in CI

Treepeat processes one file at a time, releases its source and syntax tree, and
keeps compact token sequences and fingerprints for comparisons across the entire
scan. Application code can still match installed dependencies. Files are not
excluded to meet a memory budget.

For a scan that includes installed dependencies and ignores no files:

```sh
treepeat --ruleset default detect /path/to/source \
  --similarity 90 --min-lines 15 --ignore-files '' \
  --verification-timeout 30 --max-group-pairs 100000 \
  --format sarif --output treepeat.sarif
```

Install dependencies before scanning if they are part of the intended scope.
Only supported languages and extracted regions are analyzed; a completed scan
does not imply coverage of unsupported formats such as Smarty or SCSS.

## Limits and exit codes

The CLI isolates verification in one reusable child process. A timed-out worker
is terminated and replaced so the remaining groups can be checked. The pair
limit is checked before computing a candidate group's average similarity. It
does not cap the work needed to build the LSH index and candidate connections.
Both limits accept `0` to disable them. Python API callers retain unlimited
defaults and can opt into limits with `LSHSettings` or `detect_similarity`.

| Exit code | Meaning |
| --- | --- |
| 0 | Processing completed; findings may exist. |
| 1 | `--fail` was supplied and duplicate groups were found. |
| 2 | Processing was incomplete, including a timeout or candidate limit; also used by Click for invalid arguments. |

The SARIF file is written before exiting for findings or incomplete processing.
Incomplete processing takes precedence over `--fail`. SARIF includes
`runs[].invocations[].executionSuccessful`, execution notifications, and
`runs[].properties` containing `processingComplete`, file counts, and issues.
Unresolved groups include their region locations in the issues list. Parser
syntax warnings are retained as warnings: processing can finish with partial
syntax coverage. An empty supported-file scope is a valid empty report with a
zero file count. Logs and progress go to stderr, keeping SARIF stdout valid JSON.

Add a CI job deadline and a container memory limit as outer safeguards. Per-group
limits do not bound the total number of groups, parsing time, or all memory use.
For example, with Treepeat installed in the CI environment:

```yaml
- name: Scan similarities
  timeout-minutes: 10
  run: >-
    treepeat --ruleset default detect . --similarity 90 --min-lines 15
    --ignore-files '' --format sarif --output treepeat.sarif
    --verification-timeout 30 --max-group-pairs 100000 --fail
- name: Preserve results, including incomplete scans
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: treepeat-results
    path: treepeat.sarif
```

## Matching behavior

Compact preprocessing emits the same ordered shingle strings as the annotated
display pipeline. Batched MinHash updates preserve the same fingerprints. For
long sequences, a suffix automaton finds the longest common contiguous block in
each partition, with the same earliest-in-first, then earliest-in-second tie
breaking as Python's `SequenceMatcher(autojunk=False)`. Repeated tokens retain
their meaning. Identical sequences take a direct equality path; source-signature
checks still apply under the active ruleset.

This preserves the existing order-sensitive metric and group averaging. It does
not change matching to a longest common subsequence or enable the autojunk
heuristic. Pair orientation is now sorted by region key because the existing
metric is asymmetric; this removes score variation caused by hash-set iteration
between runs. Scores can therefore differ from a previous arbitrarily ordered
run. The existing approximate LSH candidate search and transitive grouping
remain unchanged and do not guarantee exhaustive pairwise clone detection.

Each longest-block search uses linear space and linear work in that partition's
input size. Repeated partitioning can still be expensive on adversarial inputs;
the worker deadline remains necessary. See Python's
[matching and tie-breaking contract](https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher.find_longest_match).

## Regression checks

```sh
make ci
make benchmark-ci
```

The benchmark generates 512 PHP files across application and vendor directories.
It requires all 32 groups of 16 copies, a complete report, less than 512 MiB
sampled combined RSS for the scanner and its child processes, and completion
within 120 seconds. The repository CI runs this separately from unit tests.
The unit suite checks compact/annotated parity across every language fixture and
ruleset, fingerprint parity, reference matcher parity, parse-tree release,
timeout recovery, candidate limits, and partial-report exit codes.

For real-repository measurements, use the existing
[performance harness](perf-harness.md) and record the commit, installed dependency
snapshot, flags, CPU/memory constraints, elapsed time, and memory measurement
method. Keep proprietary sources and detailed findings out of public benchmark
fixtures.

## Full-repository validation

A private mixed-language PHP application snapshot, including installed
dependencies and documentation, was used without ignore patterns: 13,903
supported files, about 1.9 million lines, 96,347 extracted regions, and 25,389
regions meeting the 15-line minimum. Similarity was 90% with the default ruleset.

The original scan was stopped after 828.57 seconds during verification, with
roughly 11 GiB resident memory and substantial swap. A bounded workaround still
used about 11.7 GiB and left four groups unresolved. The optimized scan completed
in 121.81 seconds, at 779.41 MiB sampled combined scanner/worker RSS, inside a
two-CPU container limited to 4 GiB with swap disabled. This is an observed
resource comparison, not an equal-resource speedup claim: the original run did
not finish.

All 1,800 candidate groups completed verification. The 858 groups from the
previous partial report were retained, three previously unresolved groups were
added, and the fourth fell below threshold. There were no processing errors;
104 syntax-warning files were retained in the SARIF report. Syntax warnings and
unsupported formats remain coverage limitations. These measurements are for one
snapshot and do not impose a universal memory bound.
