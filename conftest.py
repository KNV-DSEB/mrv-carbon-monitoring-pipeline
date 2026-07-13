# Retained for pytest path configuration. Packaging is now handled via
# pyproject.toml (editable install).
import sys
from pathlib import Path

SRC_PATH = str(Path(__file__).parent / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# `dashboard/` lives at the repo root (per the CLAUDE.md layout), not under src/,
# so the src-layout editable install doesn't expose it. Put the repo root on
# sys.path too, so tests can `import dashboard.loaders`.
ROOT_PATH = str(Path(__file__).parent)
if ROOT_PATH not in sys.path:
    sys.path.insert(0, ROOT_PATH)
