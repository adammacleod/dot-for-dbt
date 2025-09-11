#!/usr/bin/env python3

import sys
import argparse
import subprocess

from pathlib import Path

from dot import dot, __version__
from .git import get_repo_path

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
        "--no-gitignore-check",
        action="store_true",
        default=False,
        help="Bypass .gitignore enforcement for the .dot/ directory"
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

def enforce_dot_gitignore(dbt_project_path: Path) -> None:
    """
    Ensures that the .dot/ directory is ignored in the git repository's .gitignore file.

    Args:
        dbt_project_path (Path): Path to the dbt project directory. 
                                 Used to locate the git repository root.

    Returns:
        None. Exits the process if .gitignore is missing or enforcement fails.

    Side Effects:
        May prompt the user to insert '.dot/' into .gitignore and modify the file.
        Exits the process with error if enforcement fails.
    """
    repo_path = get_repo_path(dbt_project_path)
    gitignore_path = repo_path / ".gitignore"
    dot_entry_present = False

    if gitignore_path.exists():
        with open(gitignore_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            for entry in lines:
                if entry == ".dot" or entry == ".dot/":
                    dot_entry_present = True
                    break
    else:
        logger.error(f"No .gitignore found in the git repository root ({repo_path}). Please create one and add '.dot/' to it.")
        sys.exit(1)

    if not dot_entry_present:
        logger.warning("[bold red]WARNING: dot can potentially put sensitive information into the .dot folder within your repository.[/]")
        logger.warning(
            "It is very important that this folder is [bold]never[/] committed to git, "
            "therefore, [bold]dot[/] requires that the [italic].dot/[/] folder is "
            "ignored in your .gitignore file."
        )
        logger.warning("Note: You can skip this check with the --no-gitignore-check flag, but this is not recommended for general use.")
        response = input("         Would you like to add '.dot/' to your .gitignore now? [y/N]:").strip().lower()
        if response == "y":
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n.dot/\n")
            logger.warning("Added '.dot/' to .gitignore.")
        else:
            logger.error("[yellow]Refusing to run: '.dot/' must be ignored in .gitignore for dot to run.[/]")
            sys.exit(1)

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

    if not args.no_gitignore_check:
        enforce_dot_gitignore(dbt_project_path)

    if not (dbt_project_path / "dbt_project.yml").exists():
        logger.error("[yellow]Error: You must run dot inside of a dbt project folder![/]")
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
