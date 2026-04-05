#!/usr/bin/env python3
"""Analyze accumulated observations on git commit and save patterns.
Triggered in background by observe-patterns.py.
Saves to both .omc/patterns.md AND ~/.claude auto memory system."""

import sys
import os
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


def get_memory_dir(project_root):
    """Convert project root to Claude Code auto memory path.
    /home/user/Project/MyApp -> ~/.claude/projects/-home-user-Project-MyApp/memory/
    """
    escaped = project_root.replace("/", "-")
    memory_dir = os.path.expanduser(f"~/.claude/projects/{escaped}/memory")
    return memory_dir


def save_to_auto_memory(project_root, patterns_text, commit_msg):
    """Save extracted patterns as a proper auto memory file with frontmatter."""
    memory_dir = get_memory_dir(project_root)
    os.makedirs(memory_dir, exist_ok=True)

    memory_file = os.path.join(memory_dir, "learned_patterns.md")
    memory_md = os.path.join(memory_dir, "MEMORY.md")
    project_name = os.path.basename(project_root)
    today = datetime.now().strftime("%Y-%m-%d")

    # Write/update the learned patterns memory file
    header = commit_msg.split("\n")[0][:80]
    new_entry = f"\n### {today} — {header}\n\n{patterns_text}\n"

    if os.path.exists(memory_file):
        # Append new patterns to existing file
        with open(memory_file, "r") as f:
            content = f.read()
        # Keep only last 50 entries to prevent bloat
        sections = content.split("\n### ")
        if len(sections) > 50:
            sections = sections[:1] + sections[-49:]  # Keep frontmatter + last 49
            content = "\n### ".join(sections)
        with open(memory_file, "w") as f:
            f.write(content + new_entry)
    else:
        # Create new file with frontmatter
        with open(memory_file, "w") as f:
            f.write(
                f"---\n"
                f"name: learned-patterns\n"
                f"description: 커밋 단위로 자동 학습된 도구 사용 패턴 ({project_name}). "
                f"워크플로우 습관, 도구 선호도, 에러 복구 전략 등.\n"
                f"type: feedback\n"
                f"---\n\n"
                f"# 학습된 패턴 — {project_name}\n"
                f"{new_entry}"
            )

    # Update MEMORY.md index if learned_patterns not yet listed
    if os.path.exists(memory_md):
        with open(memory_md, "r") as f:
            index_content = f.read()
        if "learned_patterns.md" not in index_content:
            with open(memory_md, "a") as f:
                f.write(
                    f"\n- [learned_patterns.md](learned_patterns.md): "
                    f"커밋 단위 자동 학습된 도구 사용 패턴\n"
                )
    else:
        with open(memory_md, "w") as f:
            f.write(
                f"# Memory Index\n\n"
                f"- [learned_patterns.md](learned_patterns.md): "
                f"커밋 단위 자동 학습된 도구 사용 패턴\n"
            )


def main():
    project_root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    obs_dir = os.path.join(project_root, ".omc", "observations")
    obs_file = os.path.join(obs_dir, "observations.jsonl")
    patterns_file = os.path.join(project_root, ".omc", "patterns.md")
    lock_file = os.path.join(obs_dir, ".analyzing")
    archive_dir = os.path.join(obs_dir, "archive")

    # Check observations exist
    if not os.path.exists(obs_file) or os.path.getsize(obs_file) == 0:
        return

    # Lock check (prevent concurrent runs)
    if os.path.exists(lock_file):
        lock_age = time.time() - os.path.getmtime(lock_file)
        if lock_age < 300:
            return
    Path(lock_file).touch()

    try:
        with open(obs_file) as f:
            lines = f.readlines()

        if len(lines) < 5:
            return  # Need minimum observations

        # Last 100 observations max
        recent = lines[-100:]

        # Project info
        project_name = os.path.basename(project_root)
        try:
            commit_msg = subprocess.check_output(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=project_root,
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            commit_msg = "unknown"

        # Build prompt
        prompt = (
            f"You are analyzing Claude Code tool usage patterns for project '{project_name}'.\n"
            f"Recent commit: {commit_msg}\n\n"
            f"Tool usage observations (JSONL):\n{''.join(recent)}\n\n"
            "Extract 2-5 actionable patterns. For each pattern:\n"
            "- What behavior was repeated or notable\n"
            "- Whether it should be project-specific or universal\n"
            "- Concrete rule to follow in future sessions\n\n"
            "Output ONLY a markdown bullet list. Be concise (max 3 lines per pattern).\n"
            "Skip trivial patterns like 'reads files' or 'uses grep'.\n"
            "Focus on: workflow sequences, error recovery, tool preferences, coding style signals.\n"
            "Write in Korean."
        )

        # Call claude CLI with haiku
        result = subprocess.check_output(
            ["claude", "-p", "--model", "haiku"],
            input=prompt.encode(),
            stderr=subprocess.DEVNULL,
            timeout=60,
        ).decode().strip()

        if not result:
            return

        # 1) Append to .omc/patterns.md (cumulative project log)
        os.makedirs(os.path.dirname(patterns_file), exist_ok=True)
        header = commit_msg.split("\n")[0][:80]
        with open(patterns_file, "a") as f:
            f.write(f"\n## {datetime.now().strftime('%Y-%m-%d')} — {header}\n\n")
            f.write(result + "\n")

        # 2) Save to auto memory (~/.claude/projects/<path>/memory/)
        save_to_auto_memory(project_root, result, commit_msg)

        # Archive processed observations
        os.makedirs(archive_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        os.rename(obs_file, os.path.join(archive_dir, f"{ts}.jsonl"))

    finally:
        try:
            os.remove(lock_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()
