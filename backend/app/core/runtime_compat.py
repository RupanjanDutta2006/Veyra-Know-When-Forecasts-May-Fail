"""Runtime compatibility and dynamic shared library resolution for cloud and serverless deployments."""
import ctypes
import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PRELOADED_LIBRARIES = set()


def ensure_linux_runtimes() -> bool:
    """Ensure essential native Linux libraries (e.g., libgomp.so.1 for LightGBM) are loaded.

    On minimal serverless environments (AWS Lambda / Vercel Python runtime),
    the GCC OpenMP runtime (libgomp.so.1) is not installed in the container image.
    This function discovers the bundled libgomp.so.1 and pre-loads it using
    ctypes.RTLD_GLOBAL so that downstream native C-extensions (such as LightGBM's
    lib_lightgbm.so) can resolve OpenMP symbols immediately without raising:
        OSError: libgomp.so.1: cannot open shared object file: No such file or directory

    On non-Linux platforms (e.g. Windows local development), this function is a safe no-op.
    """
    if sys.platform != "linux":
        return True

    if "libgomp.so.1" in _PRELOADED_LIBRARIES:
        return True

    repo_root = Path(__file__).resolve().parents[3]
    candidates = [
        Path(__file__).resolve().parent.parent / "runtimes" / "libgomp.so.1",
        repo_root / "lib" / "libgomp.so.1",
        repo_root / "backend" / "app" / "runtimes" / "libgomp.so.1",
        Path("/var/task/lib/libgomp.so.1"),
        Path("/var/task/backend/app/runtimes/libgomp.so.1"),
        Path.cwd() / "lib" / "libgomp.so.1",
    ]

    loaded_path: Optional[Path] = None
    for cand in candidates:
        if cand.is_file():
            try:
                # 1. Update LD_LIBRARY_PATH in os.environ
                cand_dir = str(cand.parent)
                current_ld = os.environ.get("LD_LIBRARY_PATH", "")
                if cand_dir not in current_ld.split(":"):
                    os.environ["LD_LIBRARY_PATH"] = (
                        f"{cand_dir}:{current_ld}" if current_ld else cand_dir
                    )

                # 2. Pre-load with RTLD_GLOBAL so all symbols are exported to the process
                ctypes.CDLL(str(cand), mode=ctypes.RTLD_GLOBAL)
                _PRELOADED_LIBRARIES.add("libgomp.so.1")
                loaded_path = cand
                logger.info("Successfully pre-loaded libgomp.so.1 from %s", cand)
                break
            except Exception as exc:
                logger.warning("Attempted to load libgomp from %s but failed: %s", cand, exc)

    if not loaded_path:
        # Fallback: check if system libgomp already exists
        try:
            ctypes.CDLL("libgomp.so.1", mode=ctypes.RTLD_GLOBAL)
            _PRELOADED_LIBRARIES.add("libgomp.so.1")
            return True
        except Exception:
            logger.warning(
                "libgomp.so.1 could not be located or pre-loaded. LightGBM import may fail on minimal Linux runtimes."
            )
            return False

    return True


# Automatically trigger on module import
ensure_linux_runtimes()
