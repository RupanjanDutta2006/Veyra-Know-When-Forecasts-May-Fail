"""Runtime compatibility and dynamic shared library resolution for cloud and serverless deployments."""
import ctypes
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_LIBGOMP_PRELOADED = False


def ensure_linux_runtimes() -> bool:
    """Ensure essential native Linux libraries (specifically libgomp.so.1 for LightGBM) are loaded.

    On minimal serverless environments (AWS Lambda / Vercel Python runtime),
    the GCC OpenMP runtime (libgomp.so.1) is not installed in the container image.
    This function discovers the bundled libgomp.so.1 and pre-loads it using
    ctypes.CDLL(..., mode=ctypes.RTLD_GLOBAL) so that downstream native C-extensions
    (such as LightGBM's lib_lightgbm.so) can resolve OpenMP symbols immediately.

    On non-Linux platforms (e.g. Windows local development), this function is a safe no-op.
    On Linux, if libgomp.so.1 cannot be located or pre-loaded, it raises a descriptive
    RuntimeError instead of failing silently.
    """
    global _LIBGOMP_PRELOADED

    # On Windows / non-Linux: completely safe no-op
    if sys.platform != "linux":
        return True

    if _LIBGOMP_PRELOADED:
        return True

    # 1. Check if system libgomp is already loaded or available in system library paths
    try:
        ctypes.CDLL("libgomp.so.1", mode=ctypes.RTLD_GLOBAL)
        _LIBGOMP_PRELOADED = True
        logger.info("System libgomp.so.1 resolved and pre-loaded globally.")
        return True
    except OSError:
        # System does not have libgomp.so.1 in standard paths; proceed to search bundled locations
        pass

    # 2. Locate bundled libgomp.so.1 using absolute repository resolution
    # __file__ is backend/app/core/runtime_compat.py
    # parents[0] = backend/app/core
    # parents[1] = backend/app
    # parents[2] = backend
    # parents[3] = repo root (/var/task in Vercel/Lambda)
    repo_root = Path(__file__).resolve().parents[3]

    candidates: List[Path] = [
        repo_root / "lib" / "libgomp.so.1",
        Path("/var/task/lib/libgomp.so.1"),
        Path.cwd() / "lib" / "libgomp.so.1",
    ]

    found_path: Optional[Path] = None
    searched_summary = []

    for cand in candidates:
        exists = cand.is_file()
        searched_summary.append(f"{cand} (exists={'YES' if exists else 'NO'})")
        if exists and found_path is None:
            found_path = cand

    if not found_path:
        error_msg = (
            f"Failed to locate bundled OpenMP runtime (libgomp.so.1) on platform '{sys.platform}'.\n"
            f"Vercel/AWS Lambda minimal Linux container requires bundled libgomp.so.1 for LightGBM.\n"
            f"Searched candidate locations:\n" + "\n".join(f"  - {s}" for s in searched_summary) + "\n"
            f"Current working directory: {Path.cwd()}\n"
            f"Repository root resolved: {repo_root}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # 3. Attempt to pre-load the discovered bundled library
    try:
        # Prepend directory to LD_LIBRARY_PATH in os.environ as secondary assurance
        cand_dir = str(found_path.parent)
        current_ld = os.environ.get("LD_LIBRARY_PATH", "")
        if cand_dir not in current_ld.split(":"):
            os.environ["LD_LIBRARY_PATH"] = (
                f"{cand_dir}:{current_ld}" if current_ld else cand_dir
            )

        # Primary load: ctypes.CDLL with RTLD_GLOBAL exports symbols globally across the process
        ctypes.CDLL(str(found_path), mode=ctypes.RTLD_GLOBAL)
        _LIBGOMP_PRELOADED = True
        logger.info("Successfully pre-loaded bundled libgomp.so.1 from %s", found_path)
        return True
    except Exception as exc:
        error_msg = (
            f"Found bundled libgomp.so.1 at '{found_path}', but ctypes.CDLL failed to load it on '{sys.platform}'.\n"
            f"Preload exception: {type(exc).__name__}: {exc}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg) from exc


# Automatically trigger on module import
ensure_linux_runtimes()
