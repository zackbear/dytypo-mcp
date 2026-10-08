"""
API keys from Windows Credential Manager instead of plaintext .env files.

Credential Manager encrypts each secret with DPAPI under your Windows login, so
it is unreadable from a synced/backed-up copy of the disk (this repo lives in
OneDrive) and never lands in git. It does not stop code already running as you.

Store or replace a key (prompts without echo, keeps it out of shell history):
    python secret_store.py set TYPESAFE_API_KEY
View/delete: Control Panel > Credential Manager > Windows Credentials > dytopo/<NAME>.
"""

from __future__ import annotations

import getpass
import sys
from typing import Mapping

TARGET_PREFIX = "dytopo/"
ERROR_NOT_FOUND = 1168  # Win32 ERROR_NOT_FOUND


def _backend():
    """(win32cred, pywintypes.error), or None off Windows / without pywin32."""
    try:
        import pywintypes
        import win32cred
    except ImportError:
        return None
    return win32cred, pywintypes.error


def read_secret(name: str) -> str | None:
    backend = _backend()
    if not backend:
        return None
    win32cred, win_error = backend
    target = TARGET_PREFIX + name
    try:
        cred = win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC)
    except win_error as e:
        if getattr(e, "winerror", None) != ERROR_NOT_FOUND:
            sys.stderr.write(f"[DyTopo] Credential Manager read of {target} failed: {e}\n")
        return None
    return cred["CredentialBlob"].decode("utf-16-le")


def write_secret(name: str, value: str) -> None:
    backend = _backend()
    if not backend:
        raise RuntimeError("Credential Manager needs Windows with pywin32 installed")
    win32cred, _ = backend
    win32cred.CredWrite({
        "Type": win32cred.CRED_TYPE_GENERIC,
        "TargetName": TARGET_PREFIX + name,
        "UserName": name,
        "CredentialBlob": value,  # pywin32 stores str as UTF-16-LE
        "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
    }, 0)


def lookup(name: str, env: Mapping[str, str]) -> str | None:
    """Environment wins (explicit override), then Credential Manager."""
    return env.get(name) or read_secret(name)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "set":
        sys.exit("usage: python secret_store.py set <NAME>")
    value = getpass.getpass(f"{sys.argv[2]}: ").strip()
    if not value:
        sys.exit("empty value, nothing stored")
    write_secret(sys.argv[2], value)
    print(f"stored {TARGET_PREFIX}{sys.argv[2]} in Windows Credential Manager")
