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
    parser.add_argument(
        "additional_params",
        nargs="*",
        help="Additional parameters to pass to dbt"
    )
    args = parser.parse_args(cli_args)

    vars_yml_path = Path(os.getcwd()) / "vars.yml"
    if not vars_yml_path.exists():
        print(f"Error: {vars_yml_path} not found.")
        sys.exit(1)

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
    context_name = args.context if args.context else default_context_name
    if context_name not in context_config:
        print(f"Error: Context '{context_name}' not found in vars.yml.")
        sys.exit(1)

    context = context_config[context_name]
    context_vars = context.get("vars", {})

    # Merge CLI arguments: context-specific overrides all
    merged_args = dict(all_args)
    for k, v in context.items():
        if k != "vars":
            merged_args[k] = v

    # Remove empty string values from vars
    filtered_vars = {k: v for k, v in context_vars.items() if v != ""}

    vars_json = json.dumps(filtered_vars)

    dbt_args = [args.dbt_command, f"--vars={vars_json}"]
    for k, v in merged_args.items():
        if isinstance(v, bool):
            if v:
                dbt_args.append(f"--{k}")
            # If false, do not add anything
        elif v is not None and v != "":
            dbt_args.append(f"--{k}")
            dbt_args.append(str(v))
    dbt_args += args.additional_params + passthrough_args

    cmd = ["dbt"] + dbt_args

    print("\033[1;32m\033[1m" + " ".join(cmd) + "\033[0m")

    if args.dry_run:
        sys.exit(0)

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
