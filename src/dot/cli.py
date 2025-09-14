#!/usr/bin/env python3

import sys
import argparse
import subprocess

from pathlib import Path

from dot import dot, __version__
from .git import get_repo_path
from .cli_prompts import run_registered_prompts, PromptAbortError

from . import logging
from .logging import get_logger

logger = get_logger('dot.cli')

def parse_args() -> tuple[argparse.Namespace, list[str]]:
    """
    Parse command-line arguments and separate passthrough args.

    Returns:
        Tuple[argparse.Namespace, List[str]]: A tuple containing the parsed arguments
        as an argparse.Namespace and a list of passthrough arguments after '--'.
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
        description="Run dbt commands with environment-based configuration from dot_environments.yml"
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
        default=False,
        help="Print the dbt command that would run, but do not execute it"
    )
    parser.add_argument(
        "--disable-prompts",
        action="store_true",
        default=False,
        help="Disable startup prompts (gitignore, editor settings) for this run"
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
        "environment",
        nargs="?",
        help="Environment name as defined in dot_environments.yml (optional, uses default if omitted, may append @<gitref>)"
    )
    args = parser.parse_args(cli_args)
    return args, passthrough_args


def app() -> int:
    """
    Main entry point for the CLI application.

    Returns:
        int: The exit code from the dbt command or error handling.

    Side Effects:
        - Parses command-line arguments.
        - Enforces .gitignore hygiene for .dot/ directory.
        - Constructs and prints the dbt command.
        - Executes the dbt command unless --dry-run is specified.
        - Handles errors and exits the process as needed.
    """

    dbt_project_path = Path.cwd()

    args, passthrough_args = parse_args()

    if args.verbose:
        logging.set_level(logging.DEBUG)

    logger.info(f"✨ [bold purple]dot-for-dbt ([cyan]v{__version__}[/])[/] ✨")

    if not (dbt_project_path / "dbt_project.yml").exists():
        logger.error("[yellow]Error: You must run dot inside of a dbt project folder![/]")
        sys.exit(1)

    try:
        repo_root = get_repo_path(dbt_project_path)
        run_registered_prompts(repo_root, args)
    except PromptAbortError as e:
        logger.error(str(e))
        sys.exit(1)

    try:
        active_environment = args.environment

        gitref = None
        if active_environment and "@" in active_environment:
            active_environment, gitref = active_environment.split("@", 1)
            active_environment = None if active_environment.strip() == '' else active_environment
            gitref = None if gitref.strip() == '' else gitref

        dbt_command = dot.dbt_command(
            dbt_command_name=args.dbt_command,
            dbt_project_path=dbt_project_path,
            active_environment=active_environment,
            passthrough_args=passthrough_args,
            gitref=gitref
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            raise
        else:
            sys.exit(1)

    if args.dry_run:
        return 0

    try:
        logger.info(f"[red]🚀  Spawning dbt 🚀[/]")
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
