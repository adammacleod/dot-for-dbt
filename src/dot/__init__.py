"""
dot-for-dbt package metadata.

Exports a __version__ attribute sourced from installed package metadata,
falling back to a placeholder when running from a local (editable) checkout
prior to an actual build/install.
"""

from importlib.metadata import version as _pkg_version, PackageNotFoundError

try:
    __version__ = _pkg_version("dot-for-dbt")
except PackageNotFoundError:
    # Fallback for local, not-yet-built editable environments.
    __version__ = "0.0.0"

__all__ = ["__version__"]
