---
name: unit-test
description: C/C++ 및 Python 프로젝트의 단위 기능 테스트 실행, 결과 분석, 배치 테스트, 파라미터 자동 탐색, 실패 원인 추적을 단계적으로 수행하는 범용 테스트 스킬
user_invocable: true
trigger: unit-test
arguments:
  - name: command
    description: "실행 명령: run, batch, auto, trace"
    required: true
  - name: target
    description: "테스트 대상 (exe 또는 py 파일명, CMake 타겟명)"
    required: true
  - name: args
    description: "테스트 인자 (이미지 경로, 파라미터 등)"
    required: false
---

# Unit Test Skill — 범용 단위 기능 테스트

C/C++ exe 및 Python 스크립트의 단위 테스트를 단계적으로 실행하고 결과를 분석합니다.

## 단계적 레벨

### Level 1: `/unit-test run <target> [args...]`
빌드(필요시) + 실행 + 결과 출력 + 사용자와 토론

### Level 2: `/unit-test batch <target> --folder <dir> [args...]`
폴더 내 파일에 반복 실행 + 통계 요약

### Level 3: `/unit-test auto <target> --folder <dir> --optimize`
파라미터 조합 자동 탐색 + 최적값 추천

### Level 4: `/unit-test trace <target> [args...]`
실패 시 /trace 연동 원인 분석

---

## Instructions

### Level 1: run (실행 + 결과 분석 + 토론)

1. **대상 파일 확인**
   - `.exe` 또는 CMake 타겟: 빌드 디렉토리에서 exe 존재 확인. 없으면 CMake 빌드 실행
   - `.py`: Python 스크립트 존재 확인

2. **빌드 (C/C++ — 필요시)**
   ```bash
   CMAKE="C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
   "$CMAKE" --build <build_dir> --config Debug --target <target>
   ```

3. **실행**
   - C/C++: `<build_dir>/Debug/<target>.exe [args...]`
   - Python: `python <script.py> [args...]`
   - PowerShell로 실행하여 exit code 캡처

4. **결과 분석**
   - stdout 전체 출력을 사용자에게 보여줌
   - 자동 판정:
     - exit code != 0 → FAIL
     - stdout에 `ERROR`, `FAIL`, `FAILED`, `NO MATCH` → FAIL
     - stdout에 `PASS`, `Found:`, `Done` → PASS
     - 판정 불가 → UNKNOWN (사용자에게 질문)
   - 수치 데이터 추출: W=, H=, Area=, Contours=, Found=, Time= 등의 패턴 파싱

5. **토론**
   - 결과를 보여주고 사용자에게 질문:
     - "파라미터를 변경해서 다시 실행할까요?"
     - "다른 이미지로 테스트할까요?"
     - "`/capture-test`로 화면을 확인할까요?"
   - 사용자 응답에 따라 파라미터 변경 후 재실행

6. **이슈 기록**
   - FAIL 시 `D:\SCTC\docs\issues_and_fixes\`에 자동 기록
   - 형식: `[OPEN] 날짜 | 심각도 | 테스트명 | 실패 내용`

---

### Level 2: batch (배치 실행)

1. **폴더 스캔**
   - `--folder` 경로에서 테스트 대상 파일 목록 생성
   - 이미지: `*.bmp *.png *.jpg *.tif`
   - 데이터: `*.csv *.json *.txt`

2. **반복 실행**
   - 각 파일에 대해 Level 1의 실행+분석 수행 (토론 없이 자동)
   - 진행률 표시: `[3/136] Processing image.bmp...`

3. **통계 요약**
   ```
   === Batch Test Summary ===
   Total: 136
   PASS: 120 (88.2%)
   FAIL: 16 (11.8%)
   
   Failed cases:
   - image_023.bmp: Found=0 (NO MATCH)
   - image_047.bmp: ERROR (threshold too high)
   ...
   ```

4. **결과 저장**
   - `<project>/test/results/batch_YYYYMMDD_HHMMSS.csv`에 결과 기록

---

### Level 3: auto (파라미터 자동 탐색)

1. **파라미터 범위 정의**
   - 사용자에게 탐색할 파라미터와 범위를 질문
   - 예: `threshold: 30~80 step 10`, `kernel: 3~15 step 2`
   - 또는 기본 범위 사용

2. **그리드 탐색**
   - 모든 파라미터 조합에 대해 Level 2 배치 실행
   - 최적 기준: PASS 비율 최대화 (또는 사용자 지정)

3. **결과 매트릭스**
   ```
   === Parameter Optimization ===
   Best: threshold=50, kernel=5, roi=500x80 → PASS 95.6%
   
   Top 5:
   1. th=50, k=5  → 95.6%
   2. th=40, k=5  → 93.4%
   3. th=50, k=7  → 91.2%
   ...
   ```

4. **추천 파라미터**를 config 파일에 저장

---

### Level 4: trace (실패 원인 분석)

1. Level 1 실행 후 FAIL이면
2. `/capture-test`로 화면 캡처 (GUI 앱인 경우)
3. 실패 원인 가설 수립:
   - 파라미터 문제? → auto로 탐색 제안
   - 이미지 문제? → 다른 이미지로 테스트 제안
   - 코드 버그? → 관련 소스코드 분석
4. 이슈 기록 + 수정 방안 제시

---

## 사용 예시

```bash
# C/C++ 테스트
/unit-test run test_blob D:/Image/Side_Left/image.bmp 50 5 800 100
/unit-test run test_cover D:/Image/Side_Left/image.bmp 50 5 80
/unit-test batch test_blob --folder D:/Image/Side_Left/ 50 5 800 100
/unit-test auto test_cover --folder D:/Image/Side_Left/ --optimize

# Python 테스트
/unit-test run test_vision.py --image D:/Image/test.bmp --threshold 50
/unit-test batch test_vision.py --folder D:/Image/Side_Left/

# 실패 추적
/unit-test trace test_blob D:/Image/Side_Left/failed_image.bmp 50 5 800 100
```

## 프로젝트 감지

- CMakeLists.txt가 있으면 C/C++ 프로젝트로 판단
- build/ 디렉토리에서 exe 탐색
- Python 스크립트는 직접 실행

## `/capture-test` 연동

Level 1 토론 중 사용자가 화면 확인을 원하면:
- `/capture-test`를 호출하여 현재 화면 캡처
- 캡처 이미지와 테스트 결과를 함께 분석
