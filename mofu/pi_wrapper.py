from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PI_AGENT_DIR = ROOT / "vendor" / "pi" / "packages" / "coding-agent"
PACKAGED_AGENT_DIR = Path(__file__).resolve().parent / "agent_runtime"


def agent_runtime_dir() -> Path:
    if (PACKAGED_AGENT_DIR / "dist" / "cli.js").exists():
        return PACKAGED_AGENT_DIR
    return SOURCE_PI_AGENT_DIR


def upstream_package_json() -> dict:
    package_json = agent_runtime_dir() / "package.json"
    if package_json.exists():
        return json.loads(package_json.read_text(encoding="utf-8"))
    return {}


def wrapper_status() -> dict:
    pkg = upstream_package_json()
    runtime = agent_runtime_dir()
    dist_cli = runtime / "dist" / "cli.js"
    src_cli = SOURCE_PI_AGENT_DIR / "src" / "cli.ts"
    return {
        "wrapped": True,
        "runtimePath": str(runtime),
        "runtimeKind": "packaged" if runtime == PACKAGED_AGENT_DIR else "source",
        "upstreamPath": str(SOURCE_PI_AGENT_DIR),
        "packageName": pkg.get("name"),
        "upstreamVersion": pkg.get("version"),
        "appName": pkg.get("piConfig", {}).get("name"),
        "configDir": pkg.get("piConfig", {}).get("configDir"),
        "distCli": str(dist_cli),
        "distBuilt": dist_cli.exists(),
        "sourceCli": str(src_cli),
        "sourceAvailable": src_cli.exists(),
        "nodeAvailable": shutil.which("node") is not None,
        "bin": pkg.get("bin", {}),
    }


def build_environment(cwd: Optional[str] = None) -> dict:
    env = dict(os.environ)
    home = Path.home()
    env.setdefault("MOFU_CODING_AGENT_DIR", str(home / ".config" / "mofumofu" / "agent"))
    env.setdefault("MOFU_CODING_AGENT_SESSION_DIR", str(home / ".local" / "state" / "mofumofu" / "sessions"))
    env.setdefault("PI_OFFLINE", "1")
    env.setdefault("MOFU_WRAPPER_CWD", str(Path(cwd or os.getcwd()).resolve()))
    return env


def agent_command(args: List[str]) -> List[str]:
    dist_cli = agent_runtime_dir() / "dist" / "cli.js"
    if dist_cli.exists():
        if shutil.which("node") is None:
            return []
        return [sys.executable, "-c", "import os,sys; os.execvp('node',['node']+sys.argv[1:])", str(dist_cli), *args]
    tsx = ROOT / "vendor" / "pi" / "node_modules" / ".bin" / "tsx"
    src_cli = SOURCE_PI_AGENT_DIR / "src" / "cli.ts"
    if tsx.exists() and src_cli.exists():
        return [str(tsx), str(src_cli), *args]
    return []


def run_agent(args: List[str], cwd: Optional[str] = None) -> int:
    cmd = agent_command(args)
    if not cmd:
        print(
            "mofu: packaged coding-agent runtime is unavailable or Node.js is not installed. "
            "Install Node.js 20+ and reinstall mofumofu, or run from source after "
            "`npm --prefix vendor/pi install` and "
            "`npm --prefix vendor/pi run build --workspace @mofumofu/coding-agent`.",
            file=sys.stderr,
        )
        return 5
    completed = subprocess.run(cmd, cwd=cwd or os.getcwd(), env=build_environment(cwd))
    return completed.returncode
