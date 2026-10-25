#!/usr/bin/env python3
"""Test runner for Windline that prevents Windows sandbox permission errors on drive root traversal."""

import os
import sys

# Monkey patch os.stat to gracefully handle sandbox restrictions on drive roots
_real_stat = os.stat

def _sandboxed_stat(path, *args, **kwargs):
    try:
        return _real_stat(path, *args, **kwargs)
    except PermissionError:
        # If traversal reaches drive root (e.g. D:\), return stat for current working directory
        p_str = str(path).rstrip("\\/").upper()
        if len(p_str) <= 2 and (len(p_str) == 0 or p_str.endswith(":")):
            return _real_stat(".", *args, **kwargs)
        raise

os.stat = _sandboxed_stat

# Also patch os.path.exists and is_file/is_dir if needed
_real_isdir = os.path.isdir
def _sandboxed_isdir(path):
    try:
        return _real_isdir(path)
    except PermissionError:
        return True
os.path.isdir = _sandboxed_isdir

if __name__ == "__main__":
    import pytest
    args = sys.argv[1:] if len(sys.argv) > 1 else ["backend/tests", "-v"]
    sys.exit(pytest.main(args))
