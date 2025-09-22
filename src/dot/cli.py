#!/usr/bin/env python3

import sys
import argparse
import subprocess

from pathlib import Path
from typing import Optional

from dot import dot, __version__
from .git import get_repo_path, get_short_commit_hash
from .config import load_config, resolve_environment, ConfigError
from .cli_prompts import run_registered_prompts, PromptAbortError

from . import logging
from .logging import get_logger

logger = get_logger('dot.cli')

def parse_env_gitref(spec: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a token of the form 'env@ref', '@ref', 'env', or 'env@'.
    Returns (environment|None, gitref|None).
    Raises ValueError for multiple '@' separators.
    """
    if spec is None:
        return (None, None)
    if spec.count('@') > 1:
        raise ValueError(f"Invalid spec '{spec}': multiple '@' separators.")
    if '@' in spec:
        env_part, ref_part = spec.split('@', 1)
    else:
        env_part, ref_part = spec, None
    env_part = env_part.strip() if env_part and env_part.strip() != '' else None
    ref_part = ref_part.strip() if ref_part and ref_part.strip() != '' else None
    return env_part, ref_part

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
    parser.add_argument(
        "--no-deps",
        action="store_true",
        default=False,
        help="Skip automatic 'dbt deps' when running against an isolated build (environment@ref or @ref)."
    )
    parser.add_argument(
        "--defer",
        dest="defer",
        metavar="env@gitref or @gitref",
        help="Defer to artifacts from a prior isolated build (git ref required)."
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
        # Parse primary environment@gitref (may omit gitref)
        try:
            active_environment, gitref = parse_env_gitref(args.environment)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

        # Pre-load config (needed for defer resolution & default environment)
        cfg = load_config(dbt_project_path)

        # Defer state resolution (commit-based only)
        defer_path: Optional[Path] = None
        if getattr(args, "defer", None):
            try:
                defer_env, defer_ref = parse_env_gitref(args.defer)
            except ValueError as e:
                logger.error(str(e))
                sys.exit(1)

            if not defer_ref:
                logger.error("`--defer` must include a git ref (use `env@gitref` or `@gitref`).")
                sys.exit(1)

            if defer_env is None:
                # Need default environment
                if cfg.default_environment is None:
                    logger.error("Cannot infer defer environment: no default environment configured.")
                    sys.exit(1)
                defer_env = cfg.default_environment

            # Validate environment existence
            try:
                resolve_environment(cfg, defer_env)
            except ConfigError:
                logger.error(f"Defer environment '{defer_env}' not defined in configuration.")
                sys.exit(1)

            try:
                short_hash = get_short_commit_hash(repo_root, defer_ref)
            except Exception as e:
                logger.error(f"git ref resolution failed: {e}")
                sys.exit(1)

            candidate = repo_root / ".dot" / "build" / short_hash / "env" / defer_env / "target"
            manifest = candidate / "manifest.json"
            if not candidate.exists():
                logger.error(f"Deferred state not found at {candidate}. Run: [bold]dot build {defer_env}@{defer_ref}[/] first.")
                sys.exit(1)
            if not manifest.exists():
                logger.error(f"Deferred state path {candidate} missing manifest.json (incomplete or never built?).")
                sys.exit(1)

            defer_path = candidate

        # If this is an isolated build (gitref provided) automatically install dependencies
        # unless user requested --no-deps or the primary command itself is 'deps' or dry-run.
        if gitref and not args.no_deps and args.dbt_command != "deps" and not args.dry_run:
            try:
                logger.info("[blue]📦 Installing dbt dependencies in isolated worktree[/]")
                deps_cmd = dot.dbt_command(
                    dbt_command_name="deps",
                    dbt_project_path=dbt_project_path,
                    active_environment=active_environment,
                    passthrough_args=[],
                    gitref=gitref,
                    defer_path=None
                )
                logger.info(f"[green]{' '.join(deps_cmd)}[/]")
                subprocess.run(deps_cmd, check=True)
            except subprocess.CalledProcessError as e:
                logger.error("[red]dbt deps failed (use --no-deps to skip)[/]")
                return e.returncode
            
        dbt_command = dot.dbt_command(
            dbt_command_name=args.dbt_command,
            dbt_project_path=dbt_project_path,
            active_environment=active_environment,
            passthrough_args=passthrough_args,
            gitref=gitref,
            defer_path=defer_path
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            raise
        else:
            sys.exit(1)

    # Log the final dbt command only once, right before potential execution (after any isolated deps installation)
    if not args.dry_run: logger.info(f"[bold red]🚀 Spawning dbt 🚀[/]")
    logger.info(f"[green]{' '.join(dbt_command)}[/]")

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
