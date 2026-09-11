import os
import sys
from pathlib import Path

# Add ecCodes / library bin to DLL directory on Windows
_BIN_DIR = Path(__file__).resolve().parents[1] / "scratch" / "env_eccodes" / "Library" / "bin"
if _BIN_DIR.exists():
    if str(_BIN_DIR) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(str(_BIN_DIR))
    except Exception:
        pass
