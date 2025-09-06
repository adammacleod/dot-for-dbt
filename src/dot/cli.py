#!/usr/bin/env python3

import sys
import argparse
import subprocess
from dot import dot
from pathlib import Path
from .git import get_repo_path


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
        "context",
        nargs="?",
        help="Context name as defined in vars.yml (optional, uses default if omitted)"
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
        print(f"Error! No .gitignore found in the git repository root ({repo_path}). Please create one and add '.dot/' to it.", file=sys.stderr)
        sys.exit(1)

    if not dot_entry_present:
        print("\033[1;33mWARNING! dot can potentially put sensitive information into the .dot folder within your repository.\033[0m")
        print(
            "\nIt is very important that this folder is *never* committed to git, "
            "as it may contain secrets or other sensitive information. Given this,"
            " dot requires that the .dot/ folder is ignored in your .gitignore file."
        )
        print("\nNote: You can skip this check with the --no-gitignore-check flag, but this is not recommended for general use.")
        response = input("\nWould you like to add '.dot/' to your .gitignore now? [y/N]: ").strip().lower()
        if response == "y":
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n.dot/\n")
            print("Added '.dot/' to .gitignore.")
        else:
            print("\033[1;31m\nRefusing to run: '.dot/' must be ignored in .gitignore for dot to run.\033[0m")
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

    if not args.no_gitignore_check:
        enforce_dot_gitignore(dbt_project_path)

    if not (dbt_project_path / "dbt_project.yml").exists():
        print("Error! You must run dot inside of a dbt project folder!", file=sys.stderr)
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
        print(f"Error: {e}", file=sys.stderr)
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
