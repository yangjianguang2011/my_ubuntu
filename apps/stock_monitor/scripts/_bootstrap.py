"""
Bootstrap helpers for standalone scripts.

Scripts in this directory are often executed directly, e.g.
`python apps/stock_monitor/scripts/foo.py`. In that mode Python only adds the
script directory to sys.path, so top-level imports such as `config` and
`stock_monitor.*` cannot be resolved unless the project `apps` directory is on
sys.path.
"""

from pathlib import Path
import sys


def ensure_project_root() -> Path:
    """Add the repository's apps directory to sys.path and return it."""
    project_root = Path(__file__).resolve().parents[2]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    return project_root
