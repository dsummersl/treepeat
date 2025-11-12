#!/usr/bin/env python3
"""
Duplication Detection Testing Framework

This script runs multiple duplication detection tools against various codebases
and generates a comprehensive comparison report.
"""

import json
import os
import subprocess
import time
import sys
from pathlib import Path
from typing import Dict, List, Any
import csv
from datetime import datetime


class DuplicationTester:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.codebases_dir = base_dir / "codebases"
        self.tools_dir = base_dir / "tools"
        self.results_dir = base_dir / "results"
        self.reports_dir = base_dir / "reports"

        # Create directories if they don't exist
        for directory in [self.codebases_dir, self.tools_dir, self.results_dir, self.reports_dir]:
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
            # Clone with depth 1 for faster cloning
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
            print(f"  ✗ Failed to clone {codebase['name']}: {e.stderr.decode()}")
            return False

    def get_codebase_stats(self, repo_path: Path) -> Dict[str, Any]:
        """Get basic stats about a codebase using cloc if available."""
        try:
            result = subprocess.run(
                ['cloc', str(repo_path), '--json'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        # Fallback: count files manually
        file_count = sum(1 for _ in repo_path.rglob('*') if _.is_file())
        return {'SUM': {'nFiles': file_count, 'code': 0}}

    def run_jscpd(self, repo_path: Path, codebase_name: str) -> Dict[str, Any]:
        """Run jscpd on a codebase."""
        print(f"    Running jscpd on {codebase_name}...")
        output_file = self.results_dir / f"{codebase_name}_jscpd.json"

        start_time = time.time()
        try:
            # Run jscpd with JSON output
            result = subprocess.run(
                ['npx', 'jscpd', str(repo_path), '--reporters', 'json', '--output', str(self.results_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )
            elapsed_time = time.time() - start_time

            # Try to read the JSON report
            jscpd_output = self.results_dir / 'jscpd-report.json'
            if jscpd_output.exists():
                with open(jscpd_output, 'r') as f:
                    data = json.load(f)
                    # Rename to codebase-specific file
                    jscpd_output.rename(output_file)

                    return {
                        'tool': 'jscpd',
                        'codebase': codebase_name,
                        'duration': elapsed_time,
                        'status': 'success',
                        'duplicates_found': len(data.get('duplicates', [])),
                        'total_clones': data.get('statistics', {}).get('total', {}).get('clones', 0),
                        'percentage': data.get('statistics', {}).get('total', {}).get('percentage', 0),
                        'output_file': str(output_file)
                    }

            return {
                'tool': 'jscpd',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'no_output',
                'duplicates_found': 0,
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

    def run_pmd_cpd(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
        """Run PMD CPD on a codebase."""
        print(f"    Running PMD CPD on {codebase_name}...")
        output_file = self.results_dir / f"{codebase_name}_pmd_cpd.xml"

        # Map our language names to PMD language names
        lang_map = {
            'Python': 'python',
            'TypeScript': 'ecmascript',
            'JavaScript': 'ecmascript',
            'Java': 'java',
            'C#': 'cs',
            'Go': 'go'
        }

        pmd_lang = lang_map.get(language, 'ecmascript')

        start_time = time.time()
        try:
            # Check if PMD is installed
            pmd_home = os.environ.get('PMD_HOME')
            if not pmd_home and not Path('/opt/pmd/bin/pmd').exists():
                return {
                    'tool': 'pmd_cpd',
                    'codebase': codebase_name,
                    'duration': 0,
                    'status': 'not_installed',
                    'duplicates_found': 0
                }

            pmd_cmd = '/opt/pmd/bin/pmd' if Path('/opt/pmd/bin/pmd').exists() else f"{pmd_home}/bin/pmd"

            result = subprocess.run(
                [pmd_cmd, 'cpd', '--dir', str(repo_path), '--language', pmd_lang,
                 '--format', 'xml', '--minimum-tokens', '50'],
                capture_output=True,
                text=True,
                timeout=300
            )
            elapsed_time = time.time() - start_time

            # Write output to file
            with open(output_file, 'w') as f:
                f.write(result.stdout)

            # Count duplications from XML
            duplicates_count = result.stdout.count('<duplication')

            return {
                'tool': 'pmd_cpd',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success',
                'duplicates_found': duplicates_count,
                'output_file': str(output_file)
            }

        except FileNotFoundError:
            return {
                'tool': 'pmd_cpd',
                'codebase': codebase_name,
                'duration': 0,
                'status': 'not_installed',
                'duplicates_found': 0
            }
        except subprocess.TimeoutExpired:
            return {
                'tool': 'pmd_cpd',
                'codebase': codebase_name,
                'duration': 300,
                'status': 'timeout',
                'duplicates_found': 0
            }
        except Exception as e:
            return {
                'tool': 'pmd_cpd',
                'codebase': codebase_name,
                'duration': time.time() - start_time,
                'status': 'error',
                'error': str(e),
                'duplicates_found': 0
            }

    def run_simian(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
        """Run Simian on a codebase."""
        print(f"    Running Simian on {codebase_name}...")
        output_file = self.results_dir / f"{codebase_name}_simian.txt"

        # Map language to file extensions
        ext_map = {
            'Python': '*.py',
            'TypeScript': '*.ts',
            'JavaScript': '*.js',
            'Java': '*.java',
            'C#': '*.cs',
            'Go': '*.go'
        }

        extension = ext_map.get(language, '*.*')

        start_time = time.time()
        try:
            # Check if simian.jar exists
            simian_jar = self.tools_dir / 'simian.jar'
            if not simian_jar.exists():
                return {
                    'tool': 'simian',
                    'codebase': codebase_name,
                    'duration': 0,
                    'status': 'not_installed',
                    'duplicates_found': 0
                }

            # Find files matching the extension
            files = list(repo_path.rglob(extension))
            if not files:
                return {
                    'tool': 'simian',
                    'codebase': codebase_name,
                    'duration': 0,
                    'status': 'no_files',
                    'duplicates_found': 0
                }

            # Simian has a limit on command line length, so batch files
            file_list = self.results_dir / f"{codebase_name}_files.txt"
            with open(file_list, 'w') as f:
                for file in files[:1000]:  # Limit to 1000 files
                    f.write(str(file) + '\n')

            result = subprocess.run(
                ['java', '-jar', str(simian_jar), '-threshold=6', f'@{file_list}'],
                capture_output=True,
                text=True,
                timeout=300
            )
            elapsed_time = time.time() - start_time

            # Write output
            with open(output_file, 'w') as f:
                f.write(result.stdout)

            # Parse output for duplicates
            duplicates_count = result.stdout.count('Found ')

            return {
                'tool': 'simian',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success',
                'duplicates_found': duplicates_count,
                'output_file': str(output_file)
            }

        except FileNotFoundError:
            return {
                'tool': 'simian',
                'codebase': codebase_name,
                'duration': 0,
                'status': 'not_installed',
                'duplicates_found': 0
            }
        except subprocess.TimeoutExpired:
            return {
                'tool': 'simian',
                'codebase': codebase_name,
                'duration': 300,
                'status': 'timeout',
                'duplicates_found': 0
            }
        except Exception as e:
            return {
                'tool': 'simian',
                'codebase': codebase_name,
                'duration': time.time() - start_time,
                'status': 'error',
                'error': str(e),
                'duplicates_found': 0
            }

    def run_tssim(self, repo_path: Path, codebase_name: str) -> Dict[str, Any]:
        """Run tssim on a codebase."""
        print(f"    Running tssim on {codebase_name}...")
        output_file = self.results_dir / f"{codebase_name}_tssim.json"

        start_time = time.time()
        try:
            tssim_path = self.tools_dir / 'tssim'
            if not tssim_path.exists():
                return {
                    'tool': 'tssim',
                    'codebase': codebase_name,
                    'duration': 0,
                    'status': 'not_installed',
                    'duplicates_found': 0
                }

            # Run tssim - we'll need to check its actual CLI once we have it
            result = subprocess.run(
                ['node', str(tssim_path / 'dist' / 'cli.js'), str(repo_path)],
                capture_output=True,
                text=True,
                timeout=300
            )
            elapsed_time = time.time() - start_time

            # Write output
            with open(output_file, 'w') as f:
                f.write(result.stdout)

            # Try to parse JSON output
            try:
                data = json.loads(result.stdout)
                duplicates_count = len(data.get('duplicates', []))
            except json.JSONDecodeError:
                duplicates_count = 0

            return {
                'tool': 'tssim',
                'codebase': codebase_name,
                'duration': elapsed_time,
                'status': 'success',
                'duplicates_found': duplicates_count,
                'output_file': str(output_file)
            }

        except FileNotFoundError:
            return {
                'tool': 'tssim',
                'codebase': codebase_name,
                'duration': 0,
                'status': 'not_installed',
                'duplicates_found': 0
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

    def run_all_tools(self, codebase: Dict[str, str]) -> List[Dict[str, Any]]:
        """Run all duplication detection tools on a codebase."""
        repo_path = self.codebases_dir / codebase['name']

        if not repo_path.exists():
            print(f"  ✗ Codebase {codebase['name']} not found")
            return []

        print(f"\n  Testing {codebase['name']} ({codebase['language']})...")

        results = []

        # Get codebase stats
        stats = self.get_codebase_stats(repo_path)

        # Run each tool
        tools = [
            ('jscpd', lambda: self.run_jscpd(repo_path, codebase['name'])),
            ('pmd_cpd', lambda: self.run_pmd_cpd(repo_path, codebase['name'], codebase['language'])),
            ('simian', lambda: self.run_simian(repo_path, codebase['name'], codebase['language'])),
            ('tssim', lambda: self.run_tssim(repo_path, codebase['name']))
        ]

        for tool_name, tool_func in tools:
            result = tool_func()
            result['language'] = codebase['language']
            result['files'] = stats.get('SUM', {}).get('nFiles', 0)
            result['lines_of_code'] = stats.get('SUM', {}).get('code', 0)
            results.append(result)
            self.results.append(result)

        return results

    def generate_report(self):
        """Generate a comprehensive comparison report."""
        print("\n" + "="*80)
        print("DUPLICATION DETECTION COMPARISON REPORT")
        print("="*80)
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
            print("-" * 80)

            # Print table header
            print(f"{'Tool':<15} {'Status':<15} {'Duration (s)':<15} {'Duplicates':<15}")
            print("-" * 80)

            for result in results:
                duration = f"{result['duration']:.2f}" if result['duration'] > 0 else "N/A"
                duplicates = str(result['duplicates_found']) if result['status'] == 'success' else result['status']

                print(f"{result['tool']:<15} {result['status']:<15} {duration:<15} {duplicates:<15}")

        # Generate CSV report
        csv_file = self.reports_dir / f"duplication_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(csv_file, 'w', newline='') as f:
            fieldnames = ['codebase', 'language', 'tool', 'status', 'duration', 'duplicates_found',
                         'files', 'lines_of_code', 'output_file']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.results)

        print(f"\n\nDetailed CSV report saved to: {csv_file}")

        # Save JSON report
        json_file = self.reports_dir / f"duplication_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': self.results
            }, f, indent=2)

        print(f"JSON report saved to: {json_file}")


def main():
    base_dir = Path(__file__).parent
    tester = DuplicationTester(base_dir)

    print("="*80)
    print("DUPLICATION DETECTION TESTING FRAMEWORK")
    print("="*80)

    # Load codebase configuration
    print("\n1. Loading codebase configuration...")
    codebases = tester.load_codebases_config()
    print(f"   Found {len(codebases)} codebases to test")

    # Clone codebases
    print("\n2. Cloning codebases...")
    for codebase in codebases:
        tester.clone_codebase(codebase)

    # Run tests
    print("\n3. Running duplication detection tests...")
    for codebase in codebases:
        tester.run_all_tools(codebase)

    # Generate report
    print("\n4. Generating report...")
    tester.generate_report()

    print("\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
