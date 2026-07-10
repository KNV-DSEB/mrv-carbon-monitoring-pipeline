# Retained for pytest path configuration. Packaging is now handled via
# pyproject.toml (editable install).
import sys
from pathlib import Path

SRC_PATH = str(Path(__file__).parent / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
