---
name: capture-test
description: 실행 중인 창을 조사·선택해 캡처한 뒤 Claude가 기능 테스트 결과를 분석하는 스킬
user_invocable: true
trigger: capture-test
arguments:
  - name: description
    description: 분석할 내용 또는 확인할 사항 (선택)
    required: false
---

# Screen Capture & Analysis Skill

현재 실행 중인 창을 먼저 조사해 리스트로 보여주고, 사용자가 고른 창(또는 화면/영역)을 캡처한 뒤 Claude가 기능 동작 여부를 분석합니다.

## Instructions

사용자가 `/capture-test`를 호출하면 다음 단계를 수행하세요.

### Step 1: 실행 중인 창 조사
현재 X11 세션의 최상위 창 목록을 조회합니다.

```bash
python3 ~/.claude/capture_screen.py --mode list
```

결과는 JSON 배열(`{id,title,x,y,w,h}`)입니다. 이를 보기 좋은 표로 사용자에게 제시하세요:

```
#   ID          크기         제목
1   0x2800008   1918x1078   Firefox — GitHub
2   0x3a00012    960x1055   Terminal
3   0x4600019   1280x800    VS Code — capture_screen.py
...
```

### Step 2: 대상 선택
사용자에게 대상을 물어보세요. 다음 응답을 모두 허용합니다:

- **번호**: `1`, `1,3` (복수 선택)
- **`all`**: 목록의 모든 창 일괄 캡처
- **제목 일부/정규식**: 예: `firefox`, `VS Code`, `Terminal|VS Code`
- **`active`** (기본): 현재 활성 창
- **`full`**: 전체 화면
- **`region <left> <top> <w> <h>`**: 좌표 영역

인자 `description`이 주어졌고 해당 문자열이 Step 1 목록의 창 제목 중 하나와만 매칭된다면, 되묻지 말고 그 창을 바로 선택해도 됩니다.

### Step 3: 캡처 실행
선택에 따라 아래 명령을 실행합니다. 저장 경로는 모두 `{프로젝트 루트}/experiments/capture/YYYYMMDD_HHMMSS_<label>.png` (디렉터리 없으면 자동 생성).

**프로젝트 루트 판별 규칙** (위에서 아래로 시도):
1. `git rev-parse --show-toplevel`이 성공하면 그 결과
2. 실패하면 현재 작업 디렉터리(CWD)
3. 쓰기 권한이 없으면 `~` 아래 `~/experiments/capture/`로 폴백

**창 ID 지정** (Step 2에서 번호/제목으로 선택한 경우)
```bash
python3 ~/.claude/capture_screen.py \
  --project "{프로젝트 루트}" \
  --mode window --window-id 0x2800008 \
  --label "firefox"
```

**활성 창**
```bash
python3 ~/.claude/capture_screen.py --project "{프로젝트 루트}" --mode active --label "active"
```

**전체 화면**
```bash
python3 ~/.claude/capture_screen.py --project "{프로젝트 루트}" --mode full --label "fullscreen"
```

**영역**
```bash
python3 ~/.claude/capture_screen.py \
  --project "{프로젝트 루트}" --mode region \
  --left 100 --top 100 --width 800 --height 600 \
  --label "region"
```

여러 창을 선택한 경우(`1,3` / `all` / 정규식 다중 매칭) 각 창마다 위 `window` 명령을 반복 실행합니다. `--label`에는 창 제목에서 영숫자/`.`/`_`/`-`만 남긴 슬러그(60자 이내)를 넣으세요.

### Step 4: 캡처 이미지 분석
Read 도구로 캡처된 이미지(들)를 읽고 다음을 분석합니다:

1. **UI 요소 확인**: 윈도우, 버튼, 메뉴, 탭 등이 정상 표시되는지
2. **에러 확인**: 에러 메시지, 팝업, 크래시 화면 유무
3. **기능 동작 확인**: 사용자가 설명한 기능이 정상 동작하는지
4. **레이아웃 확인**: UI 요소 배치가 올바른지

### Step 5: 분석 결과 보고
다음 형식으로 보고합니다:

```
## 캡처 분석 결과

**대상 창**: <제목 또는 active/full/region>
**캡처 파일**: experiments/capture/YYYYMMDD_HHMMSS_<label>.png
**캡처 모드**: window/active/full/region

### 확인 항목
- [ ] UI 정상 표시
- [ ] 에러 없음
- [ ] 기능 동작 정상
- [ ] 레이아웃 정상

### 상세 분석
(이미지에서 확인된 내용 상세 기술)

### 발견된 문제
(문제가 있으면 기술, 없으면 "발견된 문제 없음")
```

여러 창을 캡처했다면 각 창별로 위 블록을 반복합니다.

### 참고
- 사용자가 특정 확인 사항을 인자로 전달하면 해당 항목을 중점적으로 분석합니다.
- 문제 발견 시 `docs/issues_and_fixes/` 폴더에 이슈를 기록합니다.
- 분석이 완료된 캡처는 추후 별도 아카이브 폴더(예: `experiments/capture/analyzed/`)로 이동할 계획입니다. 현 단계에서는 자동 이동하지 않습니다.

#### 환경 요구
- **Linux (X11)**: `xwininfo` 필수. `xprop`가 있으면 활성 창 감지 폴백 가능. 캡처는 `Pillow(PIL)`가 있으면 추가 설치 없이 동작하며, `mss` 또는 `xdotool`이 설치돼 있으면 그 경로도 사용됩니다.
- **Windows**: 기존 `mss` + ctypes 경로 유지.
- **Wayland**: 미지원 (xwininfo 의존).
