"""Starts and stops the backend and frontend dev servers the end-to-end check drives."""
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from e2e_paths import BACKEND, FRONTEND


def port_in_use(port: int) -> bool:
    """Return True when something on this machine already listens on `port`."""
    for host in ("127.0.0.1", "::1"):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def wait_for_http(url: str, proc: subprocess.Popen, what: str, timeout: float = 90.0) -> None:
    """Poll `url` until it answers 2xx; fail early if the process died."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{what} exited with code {proc.returncode} before it was ready")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # local only
                if 200 <= response.status < 300:
                    return
        except (urllib.error.URLError, OSError):
            pass  # not up yet
        time.sleep(0.5)
    raise RuntimeError(f"{what} didn't answer {url} within {timeout:.0f}s")


def stop(proc: subprocess.Popen | None) -> None:
    """Stop a process and everything it started (npm starts node, which starts esbuild)."""
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)  # pylint: disable=no-member  # POSIX only
        except ProcessLookupError:
            pass  # already gone
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def stop_server(proc: subprocess.Popen | None) -> bool:
    """Shut the backend down the way Ctrl+C does, so its lifespan stops the agent worker.

    Returns False (after force-stopping it) when it didn't exit by itself.
    """
    if proc is None or proc.poll() is not None:
        return True
    try:
        if sys.platform == "win32":
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)  # needs CREATE_NEW_PROCESS_GROUP
        else:
            os.killpg(proc.pid, signal.SIGINT)  # pylint: disable=no-member  # POSIX only
        proc.wait(timeout=20)
        return True
    except (OSError, subprocess.TimeoutExpired):
        stop(proc)
        return False


def e2e_env(data_dir: Path, submit_real_form: bool) -> dict:
    """Return the environment both processes run with: offline, fake form, Claude off."""
    env = dict(os.environ)
    env.update({
        "AUTOAPPLY_DATA_DIR": str(data_dir),
        "FAKE_GREENHOUSE": "true",
        "ANTHROPIC_API_KEY": "",  # set but empty: agent/.env doesn't override it
        "USE_CLAUDE": "false",
        "SEED_BANK_FROM_PROFILE": "false",
        "RESUME_PARSE_STEP_MS": "0",
        "SUBMIT_REAL_FORM": "true" if submit_real_form else "false",
        "AGENT_SHOW_BROWSER": "false",
        "PYTHONUNBUFFERED": "1",
        "BROWSER": "none",  # Vite: don't open a browser window
    })
    return env


def start_processes(data_dir: Path, env: dict):
    """Start the backend and the frontend dev server; return them and their open log files."""
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32"
             else {"start_new_session": True})
    # pylint: disable=consider-using-with  # both run until main() stops them
    server_log = open(logs / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen([sys.executable, "-m", "server"], cwd=BACKEND, env=env,
                              stdout=server_log, stderr=subprocess.STDOUT, **group)
    npm = shutil.which("npm") or "npm"
    vite_log = open(logs / "vite.log", "w", encoding="utf-8")
    vite = subprocess.Popen([npm, "run", "dev:api", "--", "--strictPort"], cwd=FRONTEND, env=env,
                            stdout=vite_log, stderr=subprocess.STDOUT, **group)
    return server, vite, (server_log, vite_log)


def ensure_node_modules() -> None:
    """Run npm install when frontend/node_modules is missing."""
    if (FRONTEND / "node_modules").is_dir():
        return
    print("frontend/node_modules is missing: running npm install", flush=True)
    npm = shutil.which("npm") or "npm"
    subprocess.run([npm, "install"], cwd=FRONTEND, check=True)
