import subprocess


def is_il2_running() -> bool:
    """
    True if IL-2 is running (Windows: checks tasklist).
    Keeps Step3 independent of extra dependencies (no psutil needed).
    """
    try:
        # Windows only (your tracker is Windows-focused)
        out = subprocess.check_output(["tasklist"], text=True, errors="ignore")
        out_l = out.lower()
        return ("il-2.exe" in out_l) or ("il2.exe" in out_l)
    except Exception:
        # If detection fails, be conservative: treat as "not running"
        return False
