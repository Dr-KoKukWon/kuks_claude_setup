---
name: project-autolearn
description: >
  커밋 단위로 도구 사용 패턴을 자동 학습하는 시스템.
  PostToolUse 훅이 관찰을 기록하고, git commit 감지 시 Haiku가 패턴을 분석하여
  .omc/patterns.md와 ~/.claude auto memory에 저장합니다.
  세션 시작 시 학습된 패턴을 자동으로 참고합니다.
version: 1.0.0
---

# 패턴 학습 시스템 — 커밋 단위 자동 학습

Claude Code 세션에서 도구 사용 패턴을 자동으로 관찰하고, git commit 시점에 분석하여
재사용 가능한 워크플로우 패턴으로 변환하는 경량 학습 시스템입니다.

## 특징

- **비용 최소화**: 관찰은 셸 스크립트 수준 (비용 0), 분석은 커밋당 Haiku 1회
- **자동 동작**: 설정 후 사용자 개입 없이 완전 자동
- **auto memory 연동**: `~/.claude/projects/*/memory/`에 저장되어 다음 세션에서 자동 로드
- **프로젝트 격리**: 각 git 프로젝트별로 관찰과 패턴이 분리
- **비차단**: 분석은 백그라운드에서 실행 (작업 중단 없음)

## 작동 방식

```
도구 사용 (Read, Edit, Bash, Grep 등)
      │
      │ PostToolUse Hook (observe-patterns.py)
      │ → .omc/observations/observations.jsonl에 기록 (비용 0)
      ▼
git commit 감지
      │
      │ analyze-patterns.py (백그라운드 실행)
      │ → Haiku로 패턴 분석 (커밋당 1회)
      ▼
┌─────────────────────────────────────────┐
│  저장 위치 (이중 저장)                      │
│  1. <project>/.omc/patterns.md          │
│  2. ~/.claude/projects/*/memory/        │
│     └─ learned_patterns.md (auto memory)│
└─────────────────────────────────────────┘
      │
      │ 다음 세션 시작
      ▼
Claude가 auto memory에서 학습된 패턴을 읽고 적용
```

## 설치

### 1. 파일 복사

```bash
# 훅 스크립트 복사
cp hooks/observe-patterns.py ~/.claude/hooks/
cp hooks/analyze-patterns.py ~/.claude/hooks/

# 실행 권한 부여
chmod +x ~/.claude/hooks/observe-patterns.py
chmod +x ~/.claude/hooks/analyze-patterns.py

# 스킬 복사
mkdir -p ~/.claude/skills/pattern-learning
cp SKILL.md ~/.claude/skills/pattern-learning/
```

### 2. settings.json에 훅 등록

`~/.claude/settings.json`의 `hooks` 섹션에 추가:

```json
{
  "hooks": {
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
  }
}
```

### 3. 설치 확인

```bash
# 훅 스크립트 존재 확인
ls -la ~/.claude/hooks/observe-patterns.py
ls -la ~/.claude/hooks/analyze-patterns.py

# git 프로젝트에서 테스트
echo '{"tool_name":"Bash","tool_input":{"command":"echo test"},"tool_response":"test","cwd":"'$(pwd)'"}' | python3 ~/.claude/hooks/observe-patterns.py
cat .omc/observations/observations.jsonl
```

## 파일 구조

```
~/.claude/
├── hooks/
│   ├── observe-patterns.py   # PostToolUse 관찰자
│   └── analyze-patterns.py   # 커밋 시 패턴 분석기
└── skills/
    └── pattern-learning/
        └── SKILL.md

<project-root>/
└── .omc/
    ├── observations/
    │   ├── observations.jsonl    # 현재 관찰 로그
    │   └── archive/              # 분석 완료된 로그
    └── patterns.md               # 학습된 패턴 (커밋별 축적)

~/.claude/projects/<escaped-path>/memory/
├── MEMORY.md                     # 인덱스 (자동 업데이트)
└── learned_patterns.md           # auto memory 연동 패턴
```

## 관찰 대상 도구

| 도구 | 기록 내용 |
|------|-----------|
| Bash | 실행 명령어 (200자 제한) |
| Read | 파일 경로 |
| Write | 파일 경로 |
| Edit | 파일 경로 |
| Grep | 검색 패턴 |
| Glob | 파일 패턴 |

## 분석이 추출하는 패턴

- **워크플로우 시퀀스**: Edit → Test → Commit 같은 반복 패턴
- **도구 선호도**: 특정 작업에 선호하는 도구
- **에러 복구 전략**: 에러 발생 후 대응 패턴
- **코딩 스타일 신호**: 파일 구조, 네이밍 등

## 관리

```bash
# 학습된 패턴 확인
cat <project>/.omc/patterns.md

# 관찰 로그 크기 확인
wc -l <project>/.omc/observations/observations.jsonl

# 아카이브 정리
rm <project>/.omc/observations/archive/*.jsonl

# 패턴 초기화 (처음부터 다시 학습)
rm <project>/.omc/patterns.md
rm ~/.claude/projects/<escaped-path>/memory/learned_patterns.md
```

## .gitignore 권장

프로젝트 `.gitignore`에 추가:

```
.omc/
```

## 요구사항

- Python 3.8+
- Claude Code CLI (`claude` 명령어)
- git

## 설계 원칙

| 결정 | 이유 |
|------|------|
| 관찰은 Python (jq 불필요) | 의존성 최소화 |
| 분석은 커밋 단위 | 완성된 작업 단위가 가장 응집력 있는 패턴 생성 |
| 백그라운드 실행 | 작업 흐름 중단 없음 |
| auto memory 이중 저장 | Claude Code가 다음 세션에서 자동 로드 |
| 관찰 50건 상한 아카이브 | 메모리 파일 비대화 방지 |
| PreToolUse 제외 | 오버헤드 절반 감소, PostToolUse만으로 충분 |

## 개인정보

- 모든 관찰 데이터는 로컬에만 저장
- 실제 코드 내용은 기록하지 않음 (도구명 + 파일 경로/명령어만)
- 분석 결과(패턴)만 메모리에 저장

---

*커밋할 때마다 Claude가 당신의 작업 습관을 조금씩 배웁니다.*
