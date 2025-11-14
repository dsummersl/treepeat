#!/usr/bin/env python3
"""
Duplication Detection Testing Framework

Runs multiple duplication detection tools against various codebases
and generates comprehensive comparison reports.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any
import csv
from datetime import datetime
import hashlib
from collections import defaultdict
import argparse


class DuplicationTester:
    def __init__(self, base_dir: Path, ruleset: str = 'default'):
        self.base_dir = base_dir
        self.codebases_dir = base_dir / "codebases"
        self.results_dir = base_dir / "results"
        self.reports_dir = base_dir / "reports"
        self.tssim_root = base_dir.parent  # tssim is one level up
        self.ruleset = ruleset  # Store the ruleset to use for tssim

        for directory in [self.codebases_dir, self.results_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.results = []

    def load_codebases_config(self) -> List[Dict[str, str]]:
        """Load codebase configuration from JSON file."""
        config_file = self.base_dir / "codebases.json"
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config['codebases']

    def clone_codebase(self, codebase: Dict[str, str]) -> bool:
        """Clone a codebase if it doesn't exist."""
        repo_path = self.codebases_dir / codebase['name']

        if repo_path.exists():
            print(f"  ✓ {codebase['name']} already cloned")
            return True

        print(f"  Cloning {codebase['name']}...")
        try:
            subprocess.run(
                ['git', 'clone', '--depth', '1', codebase['url'], str(repo_path)],
                check=True,
                capture_output=True,
                timeout=300
            )
            print(f"  ✓ Cloned {codebase['name']}")
            return True
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout cloning {codebase['name']}")
            return False
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Failed to clone {codebase['name']}: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return False

    def get_file_count(self, repo_path: Path, extensions: List[str]) -> int:
        """Count files with specific extensions."""
        count = 0
        for ext in extensions:
            count += len(list(repo_path.rglob(f'*{ext}')))
        return count

    def get_line_count(self, repo_path: Path, extensions: List[str]) -> int:
        """Count lines of code."""
        total_lines = 0
        for ext in extensions:
            for file_path in repo_path.rglob(f'*{ext}'):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        total_lines += sum(1 for _ in f)
                except Exception:
                    pass
        return total_lines

    def run_tssim(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
        """Run tssim on a codebase."""
        print(f"    Running tssim on {codebase_name}...")
        output_dir = self.results_dir / f"{codebase_name}_tssim"
        output_dir.mkdir(exist_ok=True)
        json_output_file = output_dir / 'tssim-report.json'

        start_time = time.time()
        try:
            # Run tssim using uv run with JSON output
            # Use configured ruleset (default or none)
            result = subprocess.run(
                ['uv', 'run', 'tssim', str(repo_path), '--log-level', 'ERROR',
                 '--format', 'json', '--output', str(json_output_file),
                 '--ruleset', self.ruleset],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.tssim_root)
            )
            elapsed_time = time.time() - start_time

            # Try to read the JSON report
            if json_output_file.exists():
                with open(json_output_file, 'r') as f:
                    data = json.load(f)

                    # Extract metrics from JSON
                    total_similar_pairs = data.get('total_similar_pairs', 0)
                    total_regions = data.get('total_regions', 0)
                    total_files = data.get('total_files', 0)
                    failed_files = data.get('failed_files', 0)

                    return {
                        'tool': 'tssim',
                        'codebase': codebase_name,
                        'duration': elapsed_time,
                        'status': 'success',
                        'duplicates_found': total_similar_pairs,
                        'total_regions': total_regions,
                        'total_files': total_files,
                        'failed_files': failed_files,
                        'output_file': str(json_output_file),
                        'stdout': result.stdout[:500] if result.stdout else '',
                        'stderr': result.stderr[:500] if result.stderr else ''
                    }

            # No JSON output but command succeeded - fall back to console output parsing
            output = result.stdout
            duplicates_found = 0

            # Count "2 regions" lines which indicate found duplicates
            for line in output.split('\n'):
                if 'regions,' in line and 'similar' in line:
                    duplicates_found += 1

            return {
                'tool': 'tssim',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success_no_json',
                'duplicates_found': duplicates_found,
                'stdout': output[:1000] if output else '',
                'stderr': result.stderr[:500] if result.stderr else ''
            }

        except subprocess.TimeoutExpired:
            return {
                'tool': 'tssim',
                'codebase': codebase_name,
                'duration': 300,
                'status': 'timeout',
                'duplicates_found': 0
            }
        except Exception as e:
            return {
                'tool': 'tssim',
                'codebase': codebase_name,
                'duration': time.time() - start_time,
                'status': 'error',
                'error': str(e),
                'duplicates_found': 0
            }

    def run_jscpd(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
        """Run jscpd on a codebase."""
        print(f"    Running jscpd on {codebase_name}...")
        output_dir = self.results_dir / f"{codebase_name}_jscpd"
        output_dir.mkdir(exist_ok=True)

        start_time = time.time()
        try:
            # Run jscpd with JSON output
            cmd = [
                'jscpd',
                str(repo_path),
                '--reporters', 'json',
                '--output', str(output_dir),
                '--min-lines', '5',
                '--min-tokens', '50'
            ]

            # Language-specific configuration
            if language == 'Python':
                cmd.extend(['--format', 'python'])
            elif language in ['JavaScript', 'TypeScript']:
                cmd.extend(['--format', 'javascript,typescript'])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            elapsed_time = time.time() - start_time

            # Try to read the JSON report
            jscpd_output = output_dir / 'jscpd-report.json'
            if jscpd_output.exists():
                with open(jscpd_output, 'r') as f:
                    data = json.load(f)

                    statistics = data.get('statistics', {})
                    total_stats = statistics.get('total', {})

                    return {
                        'tool': 'jscpd',
                        'codebase': codebase_name,
                        'duration': elapsed_time,
                        'status': 'success',
                        'duplicates_found': total_stats.get('clones', 0),
                        'percentage': total_stats.get('percentage', 0),
                        'lines_duplicated': total_stats.get('duplicatedLines', 0),
                        'output_file': str(jscpd_output),
                        'stdout': result.stdout[:500] if result.stdout else '',
                        'stderr': result.stderr[:500] if result.stderr else ''
                    }

            # No JSON output but command succeeded
            return {
                'tool': 'jscpd',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success_no_data',
                'duplicates_found': 0,
                'percentage': 0,
                'stdout': result.stdout[:500] if result.stdout else '',
                'stderr': result.stderr[:500] if result.stderr else ''
            }

        except subprocess.TimeoutExpired:
            return {
                'tool': 'jscpd',
                'codebase': codebase_name,
                'duration': 300,
                'status': 'timeout',
                'duplicates_found': 0
            }
        except Exception as e:
            return {
                'tool': 'jscpd',
                'codebase': codebase_name,
                'duration': time.time() - start_time,
                'status': 'error',
                'error': str(e),
                'duplicates_found': 0
            }

    def run_basic_hash_detector(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
        """Run a basic hash-based duplication detector (exact file duplicates)."""
        print(f"    Running hash detector on {codebase_name}...")

        ext_map = {
            'Python': ['.py'],
            'JavaScript': ['.js', '.jsx'],
            'TypeScript': ['.ts', '.tsx']
        }
        extensions = ext_map.get(language, ['.py', '.js', '.ts'])

        start_time = time.time()
        try:
            file_hashes: Dict[str, List[Path]] = defaultdict(list)

            for ext in extensions:
                for file_path in repo_path.rglob(f'*{ext}'):
                    try:
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                            file_hashes[file_hash].append(file_path)
                    except Exception:
                        pass

            # Count duplicate groups (where hash appears more than once)
            duplicates_found = sum(1 for files in file_hashes.values() if len(files) > 1)

            elapsed_time = time.time() - start_time

            return {
                'tool': 'hash_detector',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success',
                'duplicates_found': duplicates_found,
                'total_files': sum(len(files) for files in file_hashes.values())
            }

        except Exception as e:
            return {
                'tool': 'hash_detector',
                'codebase': codebase_name,
                'duration': time.time() - start_time,
                'status': 'error',
                'error': str(e),
                'duplicates_found': 0
            }

    def test_codebase(self, codebase: Dict[str, str]) -> None:
        """Test a single codebase with all available tools."""
        repo_path = self.codebases_dir / codebase['name']

        if not repo_path.exists():
            print(f"  Skipping {codebase['name']} - not cloned")
            return

        print(f"\n  Testing {codebase['name']}...")

        # Get codebase stats
        ext_map = {
            'Python': ['.py'],
            'JavaScript': ['.js', '.jsx'],
            'TypeScript': ['.ts', '.tsx']
        }
        extensions = ext_map.get(codebase['language'], ['.py', '.js', '.ts'])

        file_count = self.get_file_count(repo_path, extensions)
        line_count = self.get_line_count(repo_path, extensions)

        print(f"    {file_count} files, {line_count:,} lines")

        # Run each tool
        tools = [
            self.run_tssim,
            self.run_jscpd,
            self.run_basic_hash_detector,
        ]

        for tool_func in tools:
            result = tool_func(repo_path, codebase['name'], codebase['language'])
            result['file_count'] = file_count
            result['line_count'] = line_count
            result['language'] = codebase['language']
            self.results.append(result)

    def generate_reports(self) -> None:
        """Generate CSV and JSON reports."""
        if not self.results:
            print("\nNo results to report")
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # CSV report
        csv_file = self.reports_dir / f'comparison_{timestamp}.csv'
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'tool', 'codebase', 'language', 'status', 'duration',
                'duplicates_found', 'percentage', 'file_count', 'line_count'
            ])
            writer.writeheader()
            for result in self.results:
                writer.writerow({
                    'tool': result.get('tool'),
                    'codebase': result.get('codebase'),
                    'language': result.get('language'),
                    'status': result.get('status'),
                    'duration': f"{result.get('duration', 0):.2f}",
                    'duplicates_found': result.get('duplicates_found', 0),
                    'percentage': result.get('percentage', ''),
                    'file_count': result.get('file_count', ''),
                    'line_count': result.get('line_count', '')
                })

        # JSON report
        json_file = self.reports_dir / f'results_{timestamp}.json'
        with open(json_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'results': self.results
            }, f, indent=2, default=str)

        print("\n✓ Reports generated:")
        print(f"  CSV: {csv_file}")
        print(f"  JSON: {json_file}")

        # Also create symlinks to latest
        latest_csv = self.reports_dir / 'latest.csv'
        latest_json = self.reports_dir / 'latest.json'

        for latest, target in [(latest_csv, csv_file), (latest_json, json_file)]:
            if latest.exists():
                latest.unlink()
            latest.symlink_to(target.name)

    def print_summary(self) -> None:
        """Print a summary of results."""
        if not self.results:
            return

        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)

        # Group by tool
        by_tool: Dict[str, List[Dict]] = defaultdict(list)
        for result in self.results:
            by_tool[result['tool']].append(result)

        for tool, results in sorted(by_tool.items()):
            successful = [r for r in results if r['status'] == 'success']
            if successful:
                avg_duration = sum(r['duration'] for r in successful) / len(successful)
                total_duplicates = sum(r.get('duplicates_found', 0) for r in successful)
                print(f"\n{tool}:")
                print(f"  Average duration: {avg_duration:.2f}s")
                print(f"  Total duplicates found: {total_duplicates}")
                print(f"  Successful runs: {len(successful)}/{len(results)}")

    def run(self) -> None:
        """Run the complete testing suite."""
        print("="*80)
        print("DUPLICATION DETECTION TESTING FRAMEWORK")
        print("="*80)

        # Load configuration
        codebases = self.load_codebases_config()
        print(f"\nLoaded {len(codebases)} codebases from config")

        # Clone codebases
        print("\n" + "-"*80)
        print("CLONING CODEBASES")
        print("-"*80)
        for codebase in codebases:
            self.clone_codebase(codebase)

        # Test each codebase
        print("\n" + "-"*80)
        print("RUNNING TESTS")
        print("-"*80)
        for codebase in codebases:
            self.test_codebase(codebase)

        # Generate reports
        print("\n" + "-"*80)
        print("GENERATING REPORTS")
        print("-"*80)
        self.generate_reports()
        self.print_summary()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run duplication detection tests')
    parser.add_argument('--ruleset', choices=['none', 'default'], default='default',
                       help='Ruleset profile to use for tssim (default: default)')
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    tester = DuplicationTester(base_dir, ruleset=args.ruleset)
    tester.run()


if __name__ == '__main__':
    main()
