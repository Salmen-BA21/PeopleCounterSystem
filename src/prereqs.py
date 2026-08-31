"""Pre-flight dependency check for pywebview on Windows.

Detects .NET Framework 4.8+ and WebView2 Runtime via the same registry
keys pywebview itself uses (see webview/platforms/winforms.py _is_chromium).
If either is missing, offers to download and install silently.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import tempfile
from pathlib import Path

import winreg

# ---------------------------------------------------------------------------
# Registry thresholds  (mirrored from pywebview winforms.py:68-127)
# ---------------------------------------------------------------------------

_DOTNET_RELEASE_MIN = 528040  # .NET Framework 4.8
_WEBVIEW2_VERSION_MIN = (86, 0, 622, 0)

_WEBVIEW2_STABLE_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

# ---------------------------------------------------------------------------
# Download URLs  (Microsoft official, lightweight bootstrappers)
# ---------------------------------------------------------------------------

_DOTNET_URL = (
    "https://go.microsoft.com/fwlink/?LinkId=2085155"  # .NET 4.8 web installer
)
_DOTNET_FILENAME = "ndp48-web.exe"

_WEBVIEW2_URL = (
    "https://go.microsoft.com/fwlink/p/?LinkId=2124703"  # WebView2 Runtime
)
_WEBVIEW2_FILENAME = "MicrosoftEdgeWebView2RuntimeInstaller.exe"

# ---------------------------------------------------------------------------
# User32 message box (no tkinter / Qt dependency)
# ---------------------------------------------------------------------------

_MB_OK = 0x00000000
_MB_ICONINFO = 0x00000040
_MB_ICONWARN = 0x00000030
_MB_YESNO = 0x00000004
_MB_ICONQUESTION = 0x00000020
_IDYES = 6


def _msgbox(text: str, title: str = "People Counter", flags: int = _MB_OK) -> int:
    """Show a blocking Win32 message box. Returns the button id."""
    return ctypes.windll.user32.MessageBoxW(0, text, title, flags)


# ---------------------------------------------------------------------------
# Registry checks
# ---------------------------------------------------------------------------


def check_dotnet() -> bool:
    """Return True if .NET Framework 4.8+ release is installed."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full",
        )
        release, _ = winreg.QueryValueEx(key, "Release")
        winreg.CloseKey(key)
        return int(release) >= _DOTNET_RELEASE_MIN
    except (OSError, ValueError):
        return False


def check_webview2() -> bool:
    """Return True if WebView2 Runtime (any channel) >= 86.0.622.0 is installed."""
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for wow in ("WOW6432Node\\", ""):
            try:
                reg_path = (
                    rf"SOFTWARE\{wow}Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_STABLE_GUID}"
                )
                key = winreg.OpenKey(hive, reg_path)
                version_str, _ = winreg.QueryValueEx(key, "pv")
                winreg.CloseKey(key)
                parts = tuple(int(p) for p in str(version_str).split(".")[:4])
                return parts >= _WEBVIEW2_VERSION_MIN
            except (OSError, ValueError, TypeError):
                continue
    return False


def check_webview2_control() -> str:
    """Check if the WebView2 interop DLLs can be located.

    Returns a status string: 'ok', 'DLL not found', or a specific error.
    This catches cases where the registry says WebView2 is installed but
    the actual interop assemblies are missing or broken.
    """
    try:
        import webview.util

        for dll_name in (
            "Microsoft.Web.WebView2.Core.dll",
            "Microsoft.Web.WebView2.WinForms.dll",
        ):
            try:
                webview.util.interop_dll_path(dll_name)
            except FileNotFoundError:
                return f"MISSING: {dll_name}"
            except Exception as exc:
                return f"ERROR locating {dll_name}: {exc}"
        return "ok"
    except ImportError:
        return "SKIP: webview.util not importable"
    except Exception as exc:
        return f"ERROR: {exc}"


def check_clr_runtime() -> str:
    """Check if pythonnet can load the CLR runtime (runs in a subprocess)."""
    code = (
        "import os, sys; os.environ.pop('PYTHONNET_RUNTIME', None);"
        " sys.modules.pop('clr', None); sys.modules.pop('pythonnet', None);"
        " try:\n"
        "    import clr; print('netfx'); sys.exit(0)\n"
        " except Exception:\n"
        "    pass\n"
        " os.environ['PYTHONNET_RUNTIME'] = 'coreclr';"
        " sys.modules.pop('clr', None); sys.modules.pop('pythonnet', None);"
        " try:\n"
        "    import clr; print('coreclr')\n"
        " except Exception as e:\n"
        "    print(f'FAIL: {e}')\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or f"FAIL: {result.stderr.strip()}"
    except Exception as exc:
        return f"ERROR: {exc}"


# ---------------------------------------------------------------------------
# Download + silent install
# ---------------------------------------------------------------------------

_PS_DOWNLOAD = (
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;"
    " Invoke-WebRequest -Uri '{url}' -OutFile '{dest}' -UseBasicParsing"
)


def _download(url: str, dest: Path) -> bool:
    """Download a file via PowerShell. Returns True on success."""
    ps_cmd = _PS_DOWNLOAD.format(url=url, dest=str(dest))
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True,
        timeout=300,
    )
    return result.returncode == 0 and dest.exists()


def _run_installer(installer: Path, description: str) -> bool:
    """Run a silent installer and wait for it to finish."""
    cmd = [str(installer)]
    if "ndp48" in installer.name.lower():
        cmd += ["/quiet", "/norestart", "/chainingpackage", "PEOPLECOUNTER"]
    elif "webview2" in installer.name.lower():
        cmd += ["/silent", "/install"]

    result = subprocess.run(cmd, capture_output=True, timeout=600)
    return result.returncode == 0


def _install_dependency(url: str, filename: str, description: str) -> bool:
    """Prompt, download, and install a single dependency. Returns True if ready."""
    resp = _msgbox(
        f"People Counter needs {description} to run as a native app.\n\n"
        f"Click Yes to download and install it now (~1.5 MB).\n"
        f"Click No to continue in your browser instead.",
        f"Install {description}?",
        _MB_YESNO | _MB_ICONQUESTION,
    )
    if resp != _IDYES:
        return False

    tmp_dir = Path(tempfile.gettempdir())
    dest = tmp_dir / filename

    # Download
    _msgbox(
        f"Downloading {description}...\nPlease wait.",
        "People Counter",
        _MB_OK | _MB_ICONINFO,
    )
    if not _download(url, dest):
        _msgbox(
            f"Download failed. Please install {description} manually:\n{url}",
            "People Counter",
            _MB_OK | _MB_ICONWARN,
        )
        return False

    # Install
    _msgbox(
        f"Installing {description}...\nThis may take a minute.",
        "People Counter",
        _MB_OK | _MB_ICONINFO,
    )
    if not _run_installer(dest, description):
        _msgbox(
            f"Installation failed. Please install {description} manually:\n{url}",
            "People Counter",
            _MB_OK | _MB_ICONWARN,
        )
        return False

    # Cleanup temp installer
    try:
        dest.unlink(missing_ok=True)
    except OSError:
        pass

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_prerequisites() -> bool:
    """Check and install missing prerequisites.

    Returns True if all dependencies are satisfied (or were just installed).
    Returns False if the user declined or installation failed — the caller
    should fall back to the browser.
    """
    if not check_dotnet():
        if not _install_dependency(_DOTNET_URL, _DOTNET_FILENAME, ".NET Framework 4.8"):
            return False

    if not check_webview2():
        if not _install_dependency(
            _WEBVIEW2_URL, _WEBVIEW2_FILENAME, "WebView2 Runtime"
        ):
            return False

    return True


def diagnose() -> str:
    """Return a human-readable diagnostic string for exe_diag.txt."""
    dotnet = check_dotnet()
    webview2 = check_webview2()
    control = check_webview2_control()
    clr = check_clr_runtime()
    parts = []
    parts.append(f".NET 4.8: {'ok' if dotnet else 'MISSING'}")
    parts.append(f"WebView2: {'ok' if webview2 else 'MISSING'}")
    parts.append(f"WebView2 DLLs: {control}")
    parts.append(f"CLR runtime: {clr}")
    if not dotnet:
        parts.append(f"  .NET install URL: {_DOTNET_URL}")
    if not webview2:
        parts.append(f"  WebView2 install URL: {_WEBVIEW2_URL}")
    return "  ".join(parts)
