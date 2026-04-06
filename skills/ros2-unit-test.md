---
name: ros2-unit-test
description: ROS2 C++ 및 Python 패키지의 빌드, 노드 실행, 토픽/서비스 테스트, 파라미터 검증, 실패 원인 추적을 단계적으로 수행하는 ROS2 전용 테스트 스킬
user_invocable: true
trigger: ros2-unit-test
arguments:
  - name: command
    description: "실행 명령: build, run, topic, service, param, trace"
    required: true
  - name: target
    description: "테스트 대상 (패키지명, 노드명, 토픽명)"
    required: true
  - name: args
    description: "추가 인자 (launch 파라미터, 토픽 데이터 등)"
    required: false
---

# ROS2 Unit Test Skill — ROS2 전용 단위 기능 테스트

ROS2 C++ 및 Python 패키지의 빌드, 노드 실행, 토픽/서비스 검증을 단계적으로 수행합니다.

## 단계적 레벨

### Level 1: `/ros2-unit-test build <package>`
colcon 빌드 + 에러 분석 + 수정 제안

### Level 2: `/ros2-unit-test run <package> [node] [args...]`
노드 실행 + 로그 분석 + 생존 확인

### Level 3: `/ros2-unit-test topic <topic_name> [--pub data] [--echo] [--hz]`
토픽 발행/구독 테스트 + 주기/데이터 검증

### Level 4: `/ros2-unit-test service <service_name> [request_data]`
서비스 호출 + 응답 검증

### Level 5: `/ros2-unit-test param <node_name> [param_name] [value]`
파라미터 조회/설정 + 검증

### Level 6: `/ros2-unit-test trace <package> [node] [args...]`
실패 시 원인 분석 (빌드 에러, 런타임 크래시, CAN 통신 등)

---

## Instructions

### Level 1: build (빌드 + 에러 분석)

1. **환경 설정**
   ```bash
   source /opt/ros/humble/setup.bash
   # 워크스페이스 install이 있으면 source
   if [ -f install/setup.bash ]; then source install/setup.bash; fi
   ```

2. **빌드 실행**
   ```bash
   colcon build --packages-select <package> 2>&1
   ```

3. **결과 분석**
   - 빌드 성공: `Finished <<< <package>` 확인
   - 빌드 실패: stderr에서 에러 추출
     - `fatal error: ... No such file or directory` → 의존성 누락
     - `undefined reference` → 링크 에러
     - `error:` → 컴파일 에러
   - 경고(warning) 목록 정리

4. **실패 시 자동 분석**
   - package.xml의 의존성과 실제 설치 패키지 비교
   - CMakeLists.txt의 find_package/target_link 검증
   - 수정 방안 제시 (사용자 승인 후 적용)

5. **이슈 기록**
   - 빌드 실패 시 `docs/issues_fixes/issues_and_fixes.md`에 기록

---

### Level 2: run (노드 실행 + 모니터링)

1. **사전 확인**
   - 패키지 빌드 여부 확인: `ros2 pkg list | grep <package>`
   - 실행 파일 존재 확인: `ros2 pkg executables <package>`

2. **노드 실행** (백그라운드, timeout 적용)
   ```bash
   # launch 파일이 있으면
   timeout <seconds> ros2 launch <package> <launch_file> [params...] 2>&1
   # 또는 직접 실행
   timeout <seconds> ros2 run <package> <executable> [args...] 2>&1
   ```

3. **생존 확인** (별도 터미널)
   ```bash
   ros2 node list  # 노드가 살아있는지
   ros2 topic list # 토픽이 생성되었는지
   ```

4. **로그 분석**
   - stdout/stderr 출력 캡처
   - 자동 판정:
     - 프로세스 crash (exit code != 0) → FAIL
     - `[ERROR]`, `terminate called`, `Segmentation fault` → FAIL
     - `[INFO]` + 정상 초기화 메시지 → PASS
     - timeout으로 종료 → PASS (노드가 계속 실행 중이었음)
   - CAN 관련 에러 특별 처리:
     - `Operation not permitted` → 권한 문제 (sudo 또는 setcap 필요)
     - `No such device` → CAN 인터페이스 미설정
     - `heartbeat fail` → CAN 통신 장애

5. **토론**
   - 결과를 보여주고 사용자에게 질문:
     - "파라미터를 변경해서 다시 실행할까요?"
     - "sudo로 재실행할까요?"
     - "CAN 인터페이스 상태를 확인할까요?"

---

### Level 3: topic (토픽 테스트)

1. **토픽 목록 확인**
   ```bash
   ros2 topic list
   ros2 topic info <topic_name> --verbose
   ```

2. **구독 테스트 (echo)**
   ```bash
   timeout 5 ros2 topic echo <topic_name> --once 2>&1
   ```
   - 데이터 수신 확인
   - 메시지 필드값 검증

3. **주기 측정 (hz)**
   ```bash
   timeout 5 ros2 topic hz <topic_name> 2>&1
   ```
   - 발행 주기 확인 (예: 100Hz 기대 → 실제 98.5Hz OK)

4. **발행 테스트 (pub)**
   ```bash
   ros2 topic pub --once <topic_name> <msg_type> "<yaml_data>"
   ```
   - 메시지 발행 후 구독 노드 반응 확인

5. **QoS 호환성 검증**
   ```bash
   ros2 topic info <topic_name> --verbose
   ```
   - Publisher/Subscriber QoS 매칭 확인
   - RELIABLE vs BEST_EFFORT 호환성

---

### Level 4: service (서비스 테스트)

1. **서비스 목록 확인**
   ```bash
   ros2 service list
   ros2 service type <service_name>
   ```

2. **서비스 호출**
   ```bash
   ros2 service call <service_name> <srv_type> "<yaml_request>"
   ```

3. **응답 검증**
   - success 필드 확인
   - 응답 데이터 정합성 검사

---

### Level 5: param (파라미터 테스트)

1. **파라미터 조회**
   ```bash
   ros2 param list <node_name>
   ros2 param get <node_name> <param_name>
   ```

2. **파라미터 설정**
   ```bash
   ros2 param set <node_name> <param_name> <value>
   ```

3. **검증**
   - 설정 전/후 노드 동작 변화 확인
   - 범위 밖 값 설정 시 에러 처리 확인

---

### Level 6: trace (실패 원인 분석)

1. Level 2 실행 후 FAIL이면
2. 에러 유형별 분석:
   - **빌드 에러**: 의존성 트리 추적, CMakeLists 분석
   - **런타임 크래시**: 코어 덤프 분석, 스택 트레이스
   - **CAN 통신 에러**: `ip link show can0`, `candump`, heartbeat 확인
   - **토픽 미수신**: QoS 불일치, 노드 미실행, 네임스페이스 차이
3. 이슈 기록 + 수정 방안 제시

---

## 사용 예시

```bash
# 빌드 테스트
/ros2-unit-test build tr_driver
/ros2-unit-test build tr_driver_msgs

# 노드 실행 테스트
/ros2-unit-test run tr_driver driving_motor_node can_interface:=can0
/ros2-unit-test run tr_driver --launch driving_motor_launch.py can_interface:=can0

# 토픽 테스트
/ros2-unit-test topic drives/joint_states --echo
/ros2-unit-test topic drives/joint_states --hz
/ros2-unit-test topic drives/joint_trajectory --pub "{joint_names: [wheel_left_joint, wheel_right_joint], points: [{velocities: [1.0, 1.0]}]}"

# 서비스 테스트
/ros2-unit-test service /driving_motor_node/motor_enable "{enable: true}"

# 파라미터 테스트
/ros2-unit-test param driving_motor_node max_rpm
/ros2-unit-test param driving_motor_node max_rpm 1000.0

# 실패 추적
/ros2-unit-test trace tr_driver driving_motor_node can_interface:=can0
```

## 환경 감지

- `package.xml` + `CMakeLists.txt` → ament_cmake (C++)
- `package.xml` + `setup.py` → ament_python (Python)
- `colcon build` 기반 빌드 시스템
- CAN 인터페이스: `ip link show type can` 으로 자동 감지

## CAN 하드웨어 테스트 (Motor Control 특화)

노드 실행 전 CAN 상태를 자동으로 확인:
```bash
# CAN 인터페이스 상태
ip -details link show can0

# CAN 트래픽 확인 (3초)
timeout 3 candump can0

# CAN 에러 카운터
ip -s link show can0
```

CAN 에러 자동 진단:
- `state ERROR-ACTIVE` → 정상
- `state ERROR-PASSIVE` → 통신 장애 (bitrate 불일치, 배선, 종단저항)
- `state BUS-OFF` → 심각한 에러 (즉시 정지 필요)
- `Operation not permitted` → `sudo setcap cap_net_raw+ep <executable>` 필요
