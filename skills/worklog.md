---
name: worklog
description: "작업 기록 관리 — 일별/주간/월간 worklog 작성 및 이슈 기록. 사용법: /worklog [week|month|issue] [설명]"
argument-hint: "[week|month|issue] [설명]"
---

# Worklog 관리 스킬

프로젝트 작업 이력을 체계적으로 기록합니다.

**인자:** $ARGUMENTS

## 서브커맨드 분기

인자를 파싱하여 아래 워크플로우 중 하나를 실행:

| 인자 | 동작 |
|------|------|
| (없음) 또는 일반 텍스트 | 일별 기록 작성/추가 |
| `week` | 주간 정리 생성 |
| `month` | 월간 정리 생성 |
| `issue 제목` | 이슈 초안 생성 + worklog 링크 |

---

## 공통: 디렉토리 자동 생성

모든 서브커맨드 실행 전 대상 디렉토리가 없으면 `mkdir -p`로 생성:
- `docs/worklog/YYYY/MM/`
- `docs/issues_and_fixes/`

---

## 1. 일별 기록 (`/worklog` 또는 `/worklog 설명`)

### 파일 경로
`docs/worklog/YYYY/MM/YYYY-MM-DD.md`

### Idempotent 규칙
- 파일이 없으면 템플릿으로 새로 생성
- 파일이 이미 있으면 `## 상세` 섹션에 새 항목 append
- 같은 날 여러 번 실행해도 안전

### 실행 순서
1. 오늘 날짜와 요일 확인
2. `git diff --stat HEAD` 및 `git log --oneline -5`로 오늘 변경 내역 수집
3. 현재 세션에서 수행한 작업 요약
4. 파일 작성 또는 append

### 일별 템플릿

```
# YYYY-MM-DD (요일)

## 작업 목록
- [ ] task1
- [x] task2

## 상세

### 1. 작업 제목
- **배경**: 왜 이 작업을 했는가
- **변경**: 무엇을 어떻게 변경했는가 (파일/패키지 단위)
- **결정**: 선택지가 있었다면 왜 이걸 선택했는가

## 이슈
- [ISSUE-NNN](../../issues_and_fixes/NNN-title.md) — 설명

## 비고
- 후속 작업, 주의사항 등
```

---

## 2. 주간 정리 (`/worklog week`)

### 파일 경로
`docs/worklog/YYYY/MM/week-NN.md` (NN = ISO week number, 월요일 시작)

### 실행 순서
1. 이번 주 ISO week 번호와 날짜 범위 계산
2. 해당 주의 일별 파일들 읽기 (`YYYY-MM-DD.md`)
3. 각 일별 파일에서 작업 목록과 이슈 추출
4. 주간 요약 생성

### 주간 템플릿

```
# Week NN (YYYY-MM-DD ~ YYYY-MM-DD)

## 주요 성과
- 성과 1
- 성과 2

## 일별 요약

| 날짜 | 주요 작업 |
|------|----------|
| MM-DD (월) | 작업 내용 |
| MM-DD (화) | 작업 내용 |

## 이슈 현황
- ISSUE-NNN: 상태 (해결완료/진행중/미해결)

## 다음 주 계획
-
```

---

## 3. 월간 정리 (`/worklog month`)

### 파일 경로
`docs/worklog/YYYY/MM/monthly-summary.md`

### 실행 순서
1. 해당 월의 주간 파일들 읽기 (`week-NN.md`)
2. 주간 파일이 없으면 일별 파일에서 직접 집계
3. `docs/issues_and_fixes/` 스캔하여 이슈 통계
4. 월간 요약 생성

### 월간 템플릿

```
# YYYY년 M월 월간 정리

## 주요 성과
-

## 주간 요약

| 주차 | 핵심 내용 |
|------|----------|
| W15 | 내용 |
| W16 | 내용 |

## 이슈 통계
- 신규: N건 / 해결: N건 / 미해결: N건

## 다음 달 방향
-
```

---

## 4. 이슈 기록 (`/worklog issue 제목`)

### 역할 분리 (중요)
- `/worklog issue`: 이슈 **초안** 생성 + worklog 링크 (경량)
- `/issue-fix`: 이슈 **정식 기록** — 진단/수정/검증 포함 (정본)
- `/worklog issue`는 `/issue-fix`를 대체하지 않음

### 이슈 번호 자동 부여
1. `docs/issues_and_fixes/` 디렉토리 스캔
2. 파일명에서 숫자 접두사 추출 (예: `017-xxx.md` → 17)
3. 최대값 + 1 = 새 번호 (3자리 zero-pad)
4. 중복 번호 방지: 같은 번호 파일이 이미 있으면 +1

### 실행 순서
1. 이슈 번호 자동 계산
2. `docs/issues_and_fixes/NNN-title.md` 생성
3. 오늘 worklog 파일의 `## 이슈` 섹션에 링크 추가
4. 이슈 파일의 `## 관련 작업`에 worklog 링크 추가

### 이슈 템플릿

```
# ISSUE-NNN: 제목

## 증상
- 무엇이 문제였는가

## 원인
- 왜 발생했는가

## 해결
- 어떻게 고쳤는가

## 검증
- [ ] SIL / HIL 라벨 명시
- [ ] 테스트 결과

## 관련 작업
- [worklog YYYY-MM-DD](../../worklog/YYYY/MM/YYYY-MM-DD.md)
```

---

## 링크 규칙

- 모든 링크는 **상대경로** 사용
- worklog → issue: `[ISSUE-NNN](../../issues_and_fixes/NNN-title.md)`
- issue → worklog: `[worklog YYYY-MM-DD](../../worklog/YYYY/MM/YYYY-MM-DD.md)`

## 완료 체크리스트

- [ ] 대상 디렉토리 존재 확인 (없으면 자동 생성)
- [ ] 파일 작성 또는 기존 파일에 append
- [ ] 양방향 링크 확인 (이슈 ↔ worklog)
- [ ] 사용자에게 결과 파일 경로 안내
