#!/bin/bash
# Pattern Learning 자동 설치 스크립트
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "=== Project Autolearn 설치 ==="

# 1. 훅 스크립트 복사
echo "[1/3] 훅 스크립트 복사..."
cp "$SCRIPT_DIR/hooks/observe-patterns.py" "$CLAUDE_DIR/hooks/"
cp "$SCRIPT_DIR/hooks/analyze-patterns.py" "$CLAUDE_DIR/hooks/"
chmod +x "$CLAUDE_DIR/hooks/observe-patterns.py"
chmod +x "$CLAUDE_DIR/hooks/analyze-patterns.py"

# 2. 스킬 복사
echo "[2/3] 스킬 복사..."
mkdir -p "$CLAUDE_DIR/skills/project-autolearn"
cp "$SCRIPT_DIR/SKILL.md" "$CLAUDE_DIR/skills/project-autolearn/"

# 3. settings.json 훅 등록 안내
echo "[3/3] settings.json 설정..."
if grep -q "observe-patterns" "$CLAUDE_DIR/settings.json" 2>/dev/null; then
    echo "  ✓ PostToolUse 훅이 이미 등록되어 있습니다."
else
    echo "  ⚠ ~/.claude/settings.json의 hooks 섹션에 다음을 추가하세요:"
    echo ""
    cat <<'HOOKJSON'
    "PostToolUse": [
      {
        "matcher": "Bash|Read|Write|Edit|Grep|Glob",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/observe-patterns.py",
            "timeout": 5
          }
        ]
      }
    ]
HOOKJSON
    echo ""
fi

echo ""
echo "=== 설치 완료 ==="
echo "Claude Code를 재시작하면 자동 학습이 시작됩니다."
echo "git 프로젝트에서 작업 후 commit하면 패턴이 분석됩니다."
