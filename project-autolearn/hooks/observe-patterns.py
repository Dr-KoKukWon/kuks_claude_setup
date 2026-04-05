#!/usr/bin/env python3
"""PostToolUse observer - logs tool usage to project-scoped JSONL.
Triggers pattern analysis on git commit detection."""

import sys
import json
import os
import subprocess
from datetime import datetime

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    tool_name = data.get("tool_name", "")
    if not tool_name:
        return

    # Detect project root
    cwd = data.get("cwd", os.getcwd())
    try:
        project_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return  # Not in a git repo

    # Ensure observation directory
    obs_dir = os.path.join(project_root, ".omc", "observations")
    os.makedirs(obs_dir, exist_ok=True)

    # Extract summary based on tool type
    tool_input = data.get("tool_input", {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except Exception:
            tool_input = {}

    summary = ""
    if tool_name == "Bash":
        summary = str(tool_input.get("command", ""))[:200]
    elif tool_name in ("Read", "Write", "Edit"):
        summary = str(tool_input.get("file_path", ""))
    elif tool_name == "Grep":
        summary = str(tool_input.get("pattern", ""))
    elif tool_name == "Glob":
        summary = str(tool_input.get("pattern", ""))
    else:
        summary = json.dumps(tool_input, ensure_ascii=False)[:200]

    # Check for errors in response
    response = str(data.get("tool_response", ""))[:200]
    has_error = any(
        kw in response.lower()
        for kw in ["error", "failed", "exception", "denied"]
    )

    # Log observation
    obs = {
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": tool_name,
        "summary": summary,
        "error": has_error,
    }

    obs_file = os.path.join(obs_dir, "observations.jsonl")
    with open(obs_file, "a") as f:
        f.write(json.dumps(obs, ensure_ascii=False) + "\n")

    # Detect git commit → trigger analysis in background
    if tool_name == "Bash" and "git commit" in summary:
        analyzer = os.path.expanduser("~/.claude/hooks/analyze-patterns.py")
        if os.path.exists(analyzer):
            subprocess.Popen(
                [sys.executable, analyzer, project_root],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )


if __name__ == "__main__":
    main()
