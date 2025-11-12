#!/usr/bin/env python3
"""
Simplified Duplication Detection Testing Framework
Works with jscpd and basic Python-based detection
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any
import csv
from datetime import datetime
import hashlib
from collections import defaultdict


class SimpleDuplicationTester:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.codebases_dir = base_dir / "codebases"
        self.results_dir = base_dir / "results"
        self.reports_dir = base_dir / "reports"

        for directory in [self.results_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.results = []

    def load_codebases_config(self) -> List[Dict[str, str]]:
        """Load codebase configuration from JSON file."""
        config_file = self.base_dir / "codebases.json"
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config['codebases']

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
                except:
                    pass
        return total_lines

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
        """
        Run a basic hash-based duplication detector.
        This detects exact duplicates by comparing file hashes.
        """
        print(f"    Running basic hash detector on {codebase_name}...")

        ext_map = {
            'Python': ['.py'],
            'JavaScript': ['.js', '.jsx'],
            'TypeScript': ['.ts', '.tsx'],
            'Mixed': ['.py', '.js', '.jsx', '.ts', '.tsx']
        }

        extensions = ext_map.get(language, ['.py', '.js', '.ts'])

        start_time = time.time()
        try:
            file_hashes = defaultdict(list)
            total_files = 0
            duplicates = []

            # Calculate hash for each file
            for ext in extensions:
                for file_path in repo_path.rglob(f'*{ext}'):
                    if file_path.is_file():
                        try:
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.md5(f.read()).hexdigest()
                                file_hashes[file_hash].append(str(file_path.relative_to(repo_path)))
                                total_files += 1
                        except:
                            pass

            # Find duplicates
            for hash_val, files in file_hashes.items():
                if len(files) > 1:
                    duplicates.append({
                        'hash': hash_val,
                        'count': len(files),
                        'files': files
                    })

            elapsed_time = time.time() - start_time

            # Save results
            output_file = self.results_dir / f"{codebase_name}_hash_detector.json"
            with open(output_file, 'w') as f:
                json.dump({
                    'total_files': total_files,
                    'duplicate_groups': len(duplicates),
                    'duplicates': duplicates
                }, f, indent=2)

            return {
                'tool': 'hash_detector',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success',
                'duplicates_found': len(duplicates),
                'total_duplicate_files': sum(d['count'] for d in duplicates),
                'output_file': str(output_file)
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

    def run_tssim(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
        """
        Run tssim on a codebase (TypeScript/JavaScript similarity detection).
        Assumes tssim is installed in the parent directory or accessible via npm.
        """
        print(f"    Running tssim on {codebase_name}...")

        # Only run on TypeScript/JavaScript codebases
        if language not in ['TypeScript', 'JavaScript', 'Mixed']:
            return {
                'tool': 'tssim',
                'codebase': codebase_name,
                'duration': 0,
                'status': 'skipped',
                'message': 'tssim only supports TypeScript/JavaScript',
                'duplicates_found': 0
            }

        start_time = time.time()
        try:
            # Try to find tssim in parent directory (if running from tssim repo)
            tssim_paths = [
                Path(__file__).parent.parent / 'dist' / 'index.js',  # If in tssim/testing-framework
                Path(__file__).parent / 'tools' / 'tssim' / 'dist' / 'index.js',  # If tssim in tools dir
            ]

            tssim_path = None
            for path in tssim_paths:
                if path.exists():
                    tssim_path = path
                    break

            if not tssim_path:
                # Try to use globally installed tssim
                try:
                    subprocess.run(['which', 'tssim'], capture_output=True, check=True)
                    tssim_cmd = 'tssim'
                except:
                    return {
                        'tool': 'tssim',
                        'codebase': codebase_name,
                        'duration': 0,
                        'status': 'not_installed',
                        'message': 'tssim not found (run npm install or build tssim)',
                        'duplicates_found': 0
                    }
            else:
                tssim_cmd = f"node {tssim_path}"

            output_dir = self.results_dir / f"{codebase_name}_tssim"
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / 'tssim_results.json'

            # Run tssim with appropriate options
            # Adjust these based on actual tssim CLI options
            cmd = f"{tssim_cmd} --path {repo_path} --output {output_file} --format json --min-lines 5"

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            elapsed_time = time.time() - start_time

            # Parse tssim output
            duplicates_found = 0
            if output_file.exists():
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    # Adjust based on actual tssim output format
                    if isinstance(data, list):
                        duplicates_found = len(data)
                    elif isinstance(data, dict):
                        duplicates_found = data.get('duplicates', 0)

            return {
                'tool': 'tssim',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success',
                'duplicates_found': duplicates_found,
                'output_file': str(output_file),
                'stdout': result.stdout[:500] if result.stdout else '',
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

    def run_line_based_detector(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
        """
        Run a line-based duplication detector.
        This detects duplicate code blocks by comparing sequences of lines.
        """
        print(f"    Running line-based detector on {codebase_name}...")

        ext_map = {
            'Python': ['.py'],
            'JavaScript': ['.js', '.jsx'],
            'TypeScript': ['.ts', '.tsx'],
            'Mixed': ['.py', '.js', '.jsx', '.ts', '.tsx']
        }

        extensions = ext_map.get(language, ['.py', '.js', '.ts'])
        min_lines = 5  # Minimum lines to consider as duplicate

        start_time = time.time()
        try:
            duplicates = []
            line_sequences = defaultdict(list)

            # Extract line sequences from each file
            for ext in extensions:
                for file_path in repo_path.rglob(f'*{ext}'):
                    if file_path.is_file():
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith(('#', '//'))]

                                # Extract sequences of min_lines length
                                for i in range(len(lines) - min_lines + 1):
                                    sequence = tuple(lines[i:i + min_lines])
                                    if sequence:
                                        line_sequences[sequence].append({
                                            'file': str(file_path.relative_to(repo_path)),
                                            'start_line': i + 1
                                        })
                        except:
                            pass

            # Find duplicates
            for sequence, locations in line_sequences.items():
                if len(locations) > 1:
                    duplicates.append({
                        'lines': len(sequence),
                        'occurrences': len(locations),
                        'locations': locations,
                        'sample': sequence[0][:100] if sequence else ''
                    })

            elapsed_time = time.time() - start_time

            # Save results
            output_file = self.results_dir / f"{codebase_name}_line_detector.json"
            with open(output_file, 'w') as f:
                json.dump({
                    'min_lines': min_lines,
                    'duplicate_sequences': len(duplicates),
                    'total_occurrences': sum(d['occurrences'] for d in duplicates),
                    'duplicates': duplicates[:100]  # Limit to first 100 for file size
                }, f, indent=2)

            return {
                'tool': 'line_detector',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success',
                'duplicates_found': len(duplicates),
                'total_occurrences': sum(d['occurrences'] for d in duplicates),
                'output_file': str(output_file)
            }

        except Exception as e:
            return {
                'tool': 'line_detector',
                'codebase': codebase_name,
                'duration': time.time() - start_time,
                'status': 'error',
                'error': str(e),
                'duplicates_found': 0
            }

    def run_all_tools(self, codebase: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run all duplication detection tools on a codebase."""
        repo_path = self.codebases_dir / codebase['name']

        if not repo_path.exists():
            print(f"  ✗ Codebase {codebase['name']} not found")
            return []

        print(f"\n  Testing {codebase['name']} ({codebase['language']})...")

        # Get codebase stats
        ext_map = {
            'Python': ['.py'],
            'JavaScript': ['.js', '.jsx'],
            'TypeScript': ['.ts', '.tsx'],
            'Mixed': ['.py', '.js', '.jsx', '.ts', '.tsx']
        }
        extensions = ext_map.get(codebase['language'], ['.py', '.js', '.ts'])

        file_count = self.get_file_count(repo_path, extensions)
        line_count = self.get_line_count(repo_path, extensions)

        print(f"    Files: {file_count}, Lines: {line_count}")

        results = []

        # Run each tool
        tools = [
            ('jscpd', lambda: self.run_jscpd(repo_path, codebase['name'], codebase['language'])),
            ('hash_detector', lambda: self.run_basic_hash_detector(repo_path, codebase['name'], codebase['language'])),
            ('line_detector', lambda: self.run_line_based_detector(repo_path, codebase['name'], codebase['language'])),
            ('tssim', lambda: self.run_tssim(repo_path, codebase['name'], codebase['language']))
        ]

        for tool_name, tool_func in tools:
            result = tool_func()
            result['language'] = codebase['language']
            result['files'] = file_count
            result['lines_of_code'] = line_count
            results.append(result)
            self.results.append(result)
            print(f"      {tool_name}: {result['status']} ({result.get('duplicates_found', 0)} duplicates)")

        return results

    def generate_report(self):
        """Generate a comprehensive comparison report."""
        print("\n" + "="*100)
        print("DUPLICATION DETECTION COMPARISON REPORT")
        print("="*100)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total tests run: {len(self.results)}")
        print()

        # Group by codebase
        codebases = {}
        for result in self.results:
            codebase = result['codebase']
            if codebase not in codebases:
                codebases[codebase] = []
            codebases[codebase].append(result)

        # Print results for each codebase
        for codebase_name, results in codebases.items():
            print(f"\n{codebase_name}")
            print("-" * 100)

            # Get codebase info
            if results:
                print(f"Language: {results[0]['language']}, Files: {results[0]['files']}, Lines: {results[0]['lines_of_code']}")
                print()

            # Print table header
            print(f"{'Tool':<20} {'Status':<20} {'Duration (s)':<15} {'Duplicates':<20} {'Details':<20}")
            print("-" * 100)

            for result in results:
                duration = f"{result['duration']:.2f}" if result['duration'] > 0 else "N/A"
                duplicates = str(result['duplicates_found']) if result['status'] in ['success', 'success_no_data'] else result['status']

                details = ""
                if 'percentage' in result and result['percentage'] > 0:
                    details = f"{result['percentage']:.1f}% duplicated"
                elif 'total_occurrences' in result:
                    details = f"{result['total_occurrences']} occurrences"
                elif 'total_duplicate_files' in result:
                    details = f"{result['total_duplicate_files']} files"

                print(f"{result['tool']:<20} {result['status']:<20} {duration:<15} {duplicates:<20} {details:<20}")

        # Generate CSV report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = self.reports_dir / f"duplication_report_{timestamp}.csv"
        with open(csv_file, 'w', newline='') as f:
            fieldnames = ['codebase', 'language', 'tool', 'status', 'duration', 'duplicates_found',
                         'files', 'lines_of_code', 'percentage', 'output_file']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.results)

        print(f"\n\nDetailed CSV report saved to: {csv_file}")

        # Save JSON report
        json_file = self.reports_dir / f"duplication_report_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': self.results,
                'summary': {
                    'total_codebases': len(codebases),
                    'total_tests': len(self.results),
                    'tools_used': list(set(r['tool'] for r in self.results))
                }
            }, f, indent=2)

        print(f"JSON report saved to: {json_file}")

        # Print summary statistics
        print("\n" + "="*100)
        print("SUMMARY STATISTICS")
        print("="*100)

        tools_summary = defaultdict(lambda: {'success': 0, 'error': 0, 'total_duration': 0, 'total_duplicates': 0})
        for result in self.results:
            tool = result['tool']
            tools_summary[tool]['success' if 'success' in result['status'] else 'error'] += 1
            tools_summary[tool]['total_duration'] += result['duration']
            tools_summary[tool]['total_duplicates'] += result.get('duplicates_found', 0)

        print(f"\n{'Tool':<20} {'Success':<10} {'Error':<10} {'Avg Duration':<15} {'Total Duplicates':<20}")
        print("-" * 100)
        for tool, stats in tools_summary.items():
            total_runs = stats['success'] + stats['error']
            avg_duration = stats['total_duration'] / total_runs if total_runs > 0 else 0
            print(f"{tool:<20} {stats['success']:<10} {stats['error']:<10} {avg_duration:<15.2f} {stats['total_duplicates']:<20}")


def main():
    base_dir = Path(__file__).parent
    tester = SimpleDuplicationTester(base_dir)

    print("="*100)
    print("DUPLICATION DETECTION TESTING FRAMEWORK")
    print("="*100)

    # Load codebase configuration
    print("\n1. Loading codebase configuration...")
    codebases = tester.load_codebases_config()
    print(f"   Found {len(codebases)} codebases to test")

    # Run tests
    print("\n2. Running duplication detection tests...")
    total_start = time.time()

    for codebase in codebases:
        tester.run_all_tools(codebase)

    total_time = time.time() - total_start

    # Generate report
    print("\n3. Generating report...")
    tester.generate_report()

    print("\n" + "="*100)
    print(f"TESTING COMPLETE (Total time: {total_time:.2f} seconds)")
    print("="*100)


if __name__ == '__main__':
    main()
