#!/usr/bin/env python3

import sys
import argparse
import subprocess
from dot import dot
from pathlib import Path
from .git import create_worktree
from pygit2 import Repository, discover_repository
from .profiles import write_isolated_profiles_yml


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
        "-v",
        "--verbose",
        action="store_true",
        help="Turns on verbose output"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the dbt command that would run, but do not execute it"
    )
    allowed_dbt_commands = [
        "build", "clean", "clone", "compile", "debug", "deps", "docs", "init",
        "list", "parse", "retry", "run", "run-operation", "seed", "show",
        "snapshot", "source", "test"
    ]
    parser.add_argument(
        "dbt_command",
        choices=allowed_dbt_commands,
        help=f"dbt command to run. Allowed: {', '.join(allowed_dbt_commands)}"
    )
    parser.add_argument(
        "context",
        nargs="?",
        help="Context name as defined in vars.yml (optional, uses default if omitted)"
    )
    args = parser.parse_args(cli_args)
    return args, passthrough_args


def app() -> int:
    """
    Main entry point for the CLI application.

    Parses command-line arguments, constructs the dbt command using context from vars.yml,
    prints the command to the terminal, and executes it unless --dry-run is specified.
    """
    args, passthrough_args = parse_args()

    dbt_project_path = Path.cwd()

    if not (dbt_project_path / "dbt_project.yml").exists():
        print("Error! You must run dot inside of a dbt project folder!")
        sys.exit(1)

    try:
        vars_yml_path = Path.cwd() / "vars.yml"
        active_context = args.context

        gitref = None
        if active_context and "@" in active_context:
            active_context, gitref = active_context.split("@", 1)
            active_context = None if active_context.strip() == '' else active_context
            gitref = None if gitref.strip() == '' else gitref

        dbt_command = dot.dbt_command(
            dbt_command_name=args.dbt_command,
            dbt_project_path=dbt_project_path,
            vars_yml_path=vars_yml_path,
            active_context=active_context,
            passthrough_args=passthrough_args,
            gitref=gitref
        )

    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            raise
        else:
            sys.exit(1)

    print(f"dbt_project_path: {dbt_project_path}")
    print("\033[1;32m\033[1m" + " ".join(dbt_command) + "\033[0m")

    if args.dry_run:
        return 0

    try:
        result = subprocess.run(
            dbt_command,
            check=True
        )
        return result.returncode
    except subprocess.CalledProcessError as e:
        return e.returncode

if __name__ == "__main__":
    try:
        sys.exit(app())
    except KeyboardInterrupt:
        sys.exit(130)
