"""Entry point for the F001MM scientific agent.

Run from the repository root:

    python main.py "Improve the performance of this matrix multiplication"

The agent files keep their original flat imports (``from compressor import ...``),
so the three paths below are added to ``sys.path`` before importing the loop.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_ENTERPRISE_DIR = _REPO_ROOT / "src" / "agents" / "enterprise"
_AGENTS_DIR = _REPO_ROOT / "src" / "agents"

for _pathDir in (_ENTERPRISE_DIR, _AGENTS_DIR, _REPO_ROOT):
    if str(_pathDir) not in sys.path:
        sys.path.insert(0, str(_pathDir))

import click


def main(userPrompt=None):
    from orchestrator import Orchestrator

    if not userPrompt:
        userPrompt = click.prompt("What should the agent investigate?")

    Orchestrator(userPrompt)


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]).strip() or None)
