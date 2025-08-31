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


def app():
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

        if gitref:
            # TODO: Push this gitref logic down into dot.dbt_command by passing gitref as an optional arg.
            # TODO: Respect --dry-run and don't create worktrees or profiles in that case.

            # If a gitref is passed, then we will checkout a clean copy of the ref into the .dot 
            # directory, create a profiles.yml to build that commit into an isolated schema
            
            # Create worktree for the gitref
            worktree_path, commit_hash_str = create_worktree(Path.cwd(), gitref)

            # Create isolated profiles.yml
            profiles_dir = (worktree_path / '..').resolve()
            write_isolated_profiles_yml(dbt_project_path, commit_hash_str, profiles_dir, active_context)

            # TODO: Eventually, find a way to add this into the context instead of using it as passthrough args.
            # Right if someone specifies an arg in their context for profiles-dir, this will get generated on the command
            # line twice.
            passthrough_args.append('--profiles-dir')
            passthrough_args.append(str(profiles_dir))

            # TODO: Eventually find a better way to set this in the context rather than via passthrough_args
            # Add target path isolation for this build
            target_path = profiles_dir / "target"
            passthrough_args.append('--target-path')
            passthrough_args.append(str(target_path))

            dbt_command = dot.dbt_command(
                args.dbt_command,
                vars_yml_path,
                active_context,
                passthrough_args
            )
        else:
            dbt_command = dot.dbt_command(
                args.dbt_command,
                vars_yml_path,
                active_context,
                passthrough_args
            )
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            raise
        else:
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
