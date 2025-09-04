# General Rules

- When accessing documentation for libraries or frameworks, always use the Context7 MCP as the primary source whenever possible.

- Always follow the instructions in CONTRIBUTING.md, and also keep this file up to date if anything changes.

- Always keep the README.md file up to date.

# Python Specific Rules

- Always use modern Python tooling and conventions (eg: [uv](https://github.com/astral-sh/uv))

- Use type hinting for all function arguments

- Always keep imports organised at the top of each python file

- Do not remove extra newlines within function bodies if they are already there. We want to let the code breathe and make it easier to read.

# Ways of Working

- Always document your major design decisions by following the standards which have been set inside of [adr](../adr), which is our Architectural Design Register. An example ADR is [0001-commit-isolated-schemas.md](../adr/0001-commit-isolated-schemas.md)

- Always create development plans before beginning work. These are stored in the [development_plans](../development_plans) folder. There is a [README](../development_plans/README.md) with guidelines for development plans. A good example development plan is [0001-commit-isolated-schemas.md](../development_plans/0001-commit-isolated-schemas.md)
