#!/usr/bin/env python3
"""Hermes SSH plugin.

Protocol:
    Read one JSON object from stdin and write one JSON object to stdout.

Example:
    echo '{"target_host":"node-1","command":"free -m"}' \\
      | python hermes_ssh_plugin.py

The plugin intentionally uses an allowlist for hosts and commands. Configure
the host allowlist with HERMES_SSH_HOSTS, for example:

    HERMES_SSH_HOSTS=node-1,node-2 python hermes_ssh_plugin.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any


DEFAULT_TIMEOUT = 15
MAX_TIMEOUT = 60

# These patterns cover common diagnostics and narrowly scoped service actions.
# Extend this list only after reviewing the command and its authorization model.
ALLOWED_COMMAND_PATTERNS = (
    re.compile(r"^free(?:\s+-[mh])?$"),
    re.compile(r"^uptime$"),
    re.compile(r"^df\s+-h$"),
    re.compile(r"^systemctl\s+status\s+[A-Za-z0-9_.@:-]+$"),
    re.compile(r"^systemctl\s+restart\s+[A-Za-z0-9_.@:-]+$"),
)


def configured_hosts() -> set[str]:
    """Return hosts allowed by HERMES_SSH_HOSTS.

    An empty variable means no host is allowed. This fail-closed behavior is
    intentional: the operator must explicitly configure the target scope.
    """

    value = os.getenv("HERMES_SSH_HOSTS", "")
    return {item.strip() for item in value.split(",") if item.strip()}


def is_allowed_command(command: str) -> bool:
    """Return whether command exactly matches one approved pattern."""

    normalized = command.strip()
    return any(pattern.fullmatch(normalized) for pattern in ALLOWED_COMMAND_PATTERNS)


def execute_remote_ssh(target_host: str, command: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Execute an approved command on an approved SSH host."""

    hosts = configured_hosts()
    if not target_host or target_host not in hosts:
        return {
            "status": "error",
            "error": "Target host is not in HERMES_SSH_HOSTS.",
        }

    if not command or not is_allowed_command(command):
        return {
            "status": "error",
            "error": "Command is not permitted by the plugin policy.",
        }

    try:
        requested_timeout = int(timeout)
    except (TypeError, ValueError):
        return {
            "status": "error",
            "error": "timeout must be an integer.",
        }

    if not 1 <= requested_timeout <= MAX_TIMEOUT:
        return {
            "status": "error",
            "error": f"timeout must be between 1 and {MAX_TIMEOUT} seconds.",
        }

    ssh_command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "--",
        target_host,
        command.strip(),
    ]

    try:
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=requested_timeout,
            check=False,
        )
    except FileNotFoundError:
        return {
            "status": "error",
            "error": "ssh executable was not found on PATH.",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": f"Command timed out after {requested_timeout} seconds.",
        }
    except OSError as exc:
        return {
            "status": "error",
            "error": f"Unable to start ssh: {exc}",
        }

    return {
        "status": "success" if result.returncode == 0 else "failed",
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def main() -> int:
    """Process one request from stdin and emit one JSON response."""

    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")

        response = execute_remote_ssh(
            target_host=str(request.get("target_host", "")),
            command=str(request.get("command", "")),
            timeout=request.get("timeout", DEFAULT_TIMEOUT),
        )
    except json.JSONDecodeError as exc:
        response = {"status": "error", "error": f"Invalid JSON input: {exc.msg}"}
    except (TypeError, ValueError) as exc:
        response = {"status": "error", "error": str(exc)}
    except Exception as exc:  # Keep the plugin protocol intact for Hermes.
        response = {"status": "error", "error": f"Unexpected error: {exc}"}

    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
