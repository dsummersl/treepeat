#!/usr/bin/env python3
"""
Script to add a new codebase to the testing framework
"""

import json
import sys
from pathlib import Path


def add_codebase(name: str, url: str, language: str, description: str):
    """Add a new codebase to the configuration."""
    config_file = Path(__file__).parent / "codebases.json"

    # Load existing config
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Check if codebase already exists
    for codebase in config['codebases']:
        if codebase['name'] == name:
            print(f"Error: Codebase '{name}' already exists in configuration")
            return False

    # Add new codebase
    new_codebase = {
        'name': name,
        'url': url,
        'language': language,
        'description': description
    }

    config['codebases'].append(new_codebase)

    # Save updated config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"✓ Added codebase '{name}' to configuration")
    print(f"  URL: {url}")
    print(f"  Language: {language}")
    print(f"  Description: {description}")
    print("\nTo test this codebase, run:")
    print("  python3 simple_test_runner.py")

    return True


def list_codebases():
    """List all configured codebases."""
    config_file = Path(__file__).parent / "codebases.json"

    with open(config_file, 'r') as f:
        config = json.load(f)

    print("Configured Codebases:")
    print("-" * 80)
    for i, codebase in enumerate(config['codebases'], 1):
        print(f"{i}. {codebase['name']} ({codebase['language']})")
        print(f"   URL: {codebase['url']}")
        print(f"   Description: {codebase['description']}")
        print()


def main():
    if len(sys.argv) == 1 or sys.argv[1] == 'list':
        list_codebases()
    elif sys.argv[1] == 'add':
        if len(sys.argv) != 6:
            print("Usage: python3 add_codebase.py add <name> <url> <language> <description>")
            print("\nExample:")
            print("  python3 add_codebase.py add requests https://github.com/psf/requests.git Python 'HTTP library for Python'")
            sys.exit(1)

        _, _, name, url, language, description = sys.argv
        add_codebase(name, url, language, description)
    else:
        print("Usage:")
        print("  python3 add_codebase.py list              # List all codebases")
        print("  python3 add_codebase.py add <name> <url> <language> <description>  # Add new codebase")


if __name__ == '__main__':
    main()
