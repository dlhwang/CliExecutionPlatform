# 작업 단위 간 의존성 매트릭스 (Unit of Work Dependencies)

본 문서는 정의된 5개 개발 유닛(Unit of Work) 간의 빌드타임 및 런타임 의존 관계를 명세하여 개발 및 릴리즈 순서를 정의합니다.

---

## 1. 유닛 의존성 매트릭스 (Dependency Matrix)

| 호출/의존 유닛 (Caller Unit) | Unit 1 (Core & Storage) | Unit 2 (Parser & Validator) | Unit 3 (CLI Runner) | Unit 4 (SSE Streaming) | Unit 5 (Orchestrator) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Unit 1: Core & Storage** | - | | | | |
| **Unit 2: Parser & Validator** | | - | | | |
| **Unit 3: CLI Runner** | **런타임 의존** | | - | | |
| **Unit 4: SSE Streaming** | **빌드/런타임 의존** | | | - | |
| **Unit 5: Orchestrator** | **빌드/런타임 의존** | **빌드/런타임 의존** | **빌드/런타임 의존** | **빌드/런타임 의존** | - |

- **빌드/런타임 의존 (Build/Runtime Dependency)**: 해당 유닛의 코드가 올바르게 Import되거나 인터페이스가 컴파일되는 데 필요한 의존성입니다.
- **런타임 의존 (Runtime Dependency)**: 실행 중 동적인 파일 I/O 및 디렉토리 결정을 위해 필요한 의존성입니다.

---

## 2. 개발 및 배포 순서 제안 (Execution Sequence)

의존성 매트릭스에 근거하여 개발은 순차적으로 아래 방향성을 따라 진행되어야 합니다.

```
                  [Unit 2: Parser & Validator]
                               |
                               | (의존)
                               v
+----------------------------+   +-----------------------+
| Unit 1: API Core & Storage |   |  Unit 3: CLI Runner   |
+----------------------------+   +-----------------------+
       |                                     |
       +-----------------+-------------------+
                         |
                         v (의존)
             [Unit 4: SSE Streaming]
                         |
                         v (의존)
             [Unit 5: Orchestrator]
```

1. **1단계: Unit 1 & Unit 2 개발 (병렬 개발 가능)**:
   - `StorageService` 및 API 베이스(Unit 1)와 LLM 검증기(Unit 2)는 상호 의존성이 없으므로 각각 최하단 레이어로서 병렬 설계 및 코딩이 가능합니다.
2. **2단계: Unit 3 개발**:
   - `CLIExecutionRunner`는 Workspace 경로 해석을 위해 `StorageService`에 런타임 의존하므로, Unit 1이 완성된 후 개발을 개시합니다.
3. **3단계: Unit 4 개발**:
   - SSE 로깅 및 스트리밍은 DB 연결 및 `event_logs` DB 스키마 모델(Unit 1)에 의존하므로, Unit 1의 영속화 레이어가 완비된 상태에서 개발합니다.
4. **4단계: Unit 5 개발 (최종 통합)**:
   - `JobOrchestratorService`는 전송, 검증, 실행, 스토리지 등 모든 핵심 유닛의 시그니처를 조합하여 오케스트레이션을 완성해야 하므로, Unit 1~4가 모두 완성되고 단위 테스트가 확보된 후 가장 마지막에 통합 개발합니다.
