#!/usr/bin/env python3

import sys
import argparse
import subprocess
from dot import dot
from pathlib import Path

def parse_args():
    """
    Parse command-line arguments and separate passthrough args.

    Returns:
        argparse.Namespace: Parsed arguments.
        List[str]: Passthrough arguments after '--'.
    """

    argv = sys.argv[1:]

    if '--' in argv:
        idx = argv.index('--')
        cli_args = argv[:idx]
        passthrough_args = argv[idx+1:]
    else:
        cli_args = argv
        passthrough_args = []

    parser = argparse.ArgumentParser(
        description="Run dbt commands with context-based vars from vars.yml"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the dbt command that would run, but do not execute it"
    )
    parser.add_argument(
        "dbt_command",
        help="dbt command to run (e.g. build, run, test)"
    )
    parser.add_argument(
        "context",
        nargs="?",
        help="Context name as defined in vars.yml (optional, uses default if omitted)"
    )
    args = parser.parse_args(cli_args)
    return args, passthrough_args

def app():
    """
    Main entry point for the CLI application.

    Parses command-line arguments, constructs the dbt command using context from vars.yml,
    prints the command to the terminal, and executes it unless --dry-run is specified.
    """
    args, passthrough_args = parse_args()

    try:
        vars_yml_path = Path.cwd() / "vars.yml"
        dbt_command = dot.dbt_command(
            args.dbt_command,
            vars_yml_path,
            args.context,
            passthrough_args
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("\033[1;32m\033[1m" + " ".join(dbt_command) + "\033[0m")

    if args.dry_run:
        sys.exit(0)

    try:
        result = subprocess.run(dbt_command, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
