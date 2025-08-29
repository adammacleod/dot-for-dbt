#!/usr/bin/env python3

import os
import subprocess
import yaml
import json
from pathlib import Path
import argparse
import sys

def app():
    # Split sys.argv at the first standalone '--'
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

    vars_yml_path = Path(os.getcwd()) / "vars.yml"
    config = {}
    context_config = {}
    all_args = {}

    if vars_yml_path.exists():
        try:
            with open(vars_yml_path, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"Error reading vars.yml: {e}")
            sys.exit(1)
        context_config = config.get("context", {})
        default_context_name = context_config.get("default")
        all_args = context_config.get("all", {})

    # Determine context name (use default if not provided)
    context_name = args.context if args.context else context_config.get("default", None)
    if args.context and (not context_config or context_name not in context_config):
        print(f"Error: Context '{context_name}' not found in vars.yml.")
        sys.exit(1)

    context = context_config.get(context_name, {})

    # Merge CLI arguments: context-specific overrides all
    merged_args = dict(all_args)
    for k, v in context.items():
        if k != "vars":
            merged_args[k] = v

    # Remove empty string values from vars
    filtered_vars = {k: v for k, v in context.get("vars", {}).items() if v != ""}

    vars_json = json.dumps(filtered_vars)

    dbt_command = ['dbt', args.dbt_command]

    if len(filtered_vars) > 0:
        dbt_command.append(f'--vars={vars_json}')

    for k, v in merged_args.items():
        if isinstance(v, bool):
            if v:
                dbt_command.append(f"--{k}")
            # If false, do not add anything
        elif v is not None and v != "":
            dbt_command.append(f"--{k}")
            dbt_command.append(str(v))

    dbt_command += passthrough_args

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
