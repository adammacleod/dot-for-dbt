# Contributing to dot

Thank you for your interest in contributing to dot! Your help is greatly appreciated. This guide will help you get started and understand the conventions and processes for contributing to the project.

## Code of Conduct

Please be respectful and considerate in all interactions. We welcome contributions from everyone.

## Code Structure

- CLI handling is in `src/dot/cli.py`.
- All reusable logic (config loading, context resolution, command construction) is in `src/dot/dot.py`.

## Getting Started

### Local Install for Development

Installs `dc` in your system from this directory. The -e option makes uv automatically update the installed app for any code changes in the repository.

```bash
uv tool install . -e
```

### Running Tests

After any code changes, always run:

```bash
cd example_dbt_project
dot build prod
```

## Contributing Guidelines

- Open an issue to discuss any major changes before submitting a pull request.
- Follow modern Python tooling and conventions (e.g., [uv](https://github.com/astral-sh/uv)).
- Keep the codebase clean and well-documented.
- Update the README.md and this file if your changes affect usage or development.
- Document major design decisions using an ADR (Architectural Decision Register). See the [adr/](adr/) directory for existing decisions, including [ADR 0001: Commit Isolated Schemas for dbt Builds](adr/0001-commit-isolated-schemas.md), which describes the commit isolated schemas workflow.

## How to Get Help

If you have questions, open an issue or start a discussion in the repository.

We look forward to your contributions!
