# 사용자 스토리 명세서 (User Stories)

본 문서는 **하이브리드 분할 방식 (사용자 여정 + 백엔드 기능)**에 기반하여 작성된 **LLM 기반 Workspace CLI Execution Platform**의 사용자 스토리 목록입니다. 모든 스토리는 INVEST 기준을 준수하며 페르소나 `김민수 (Minsu Kim)`와 매핑됩니다.

---

## 1. 사용자 여정 기준 스토리 (User Journey-Based Stories)

### Story S-1: 자연어 기반 설계 Job 요청

**As a** 김민수 (Minsu Kim),  
**I want** 자연어 묘사(예: "샤오미 워치 S4 충전 도크")를 작성하여 플랫폼에 설계를 요청하고,  
**So that** 나의 설계 요청이 고유한 Job ID와 함께 성공적으로 등록되고 전용 작업 공간(Workspace)이 확보되기를 바란다.

#### Acceptance Criteria
- **Given**: 민수가 자연어 설명과 함께 설계 생성을 요청하면,
- **When**: 서버가 요청을 접수할 때,
- **Then**: 
  - 서버는 즉시 고유한 `Job ID`를 발급하고 데이터베이스에 Job 상태를 `CREATED`로 저장한다.
  - 서버 파일 시스템 내에 `jobs/{job_id}` 경로의 격리된 전용 디렉토리(Workspace)가 생성된다.
  - 민수에게는 Job ID 및 실시간 로그 수신을 위한 SSE Endpoint URL이 반환된다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration
- **Required Test Evidence**: `test_job_creation` API 테스트 케이스에서 POST 요청 시 201 상태코드와 Job ID를 반환받는지 확인하고, 실제 서버 디렉토리에 해당 폴더가 생성되었는지 검증한다.

---

### Story S-2: 실시간 진행 상황 및 로그 모니터링

**As a** 김민수 (Minsu Kim),  
**I want** 나의 설계 Job의 진행 단계와 OpenSCAD CLI의 빌드 로그를 실시간으로 모니터링하고 싶다,  
**So that** 서버가 현재 어떤 작업을 수행 중인지(LLM 계획 생성 중, 렌더링 중 등) 시각적으로 파악하여 답답함을 해소하고 싶다.

#### Acceptance Criteria
- **Given**: 민수의 Job이 실행 중(`RUNNING`)인 상태에서,
- **When**: 민수가 발급받은 SSE Endpoint(`/api/v1/jobs/{job_id}/stream`)를 구독할 때,
- **Then**: 
  - 서버는 LLM의 액션 실행 내용 및 OpenSCAD CLI 실행 중 발생하는 stdout/stderr 실시간 로그를 SSE 이벤트 포맷(`event: log`, `data: ...`)으로 실시간 전송한다.
  - 스트리밍되는 모든 로그는 PostgreSQL의 `event_logs` 테이블에 순차적으로(ID 및 타임스탬프와 함께) 영구 기록된다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration
- **Required Test Evidence**: `test_sse_streaming`에서 클라이언트가 SSE 구독을 개시한 뒤, 백그라운드 태스크가 이벤트를 발생시킬 때 클라이언트가 SSE 포맷의 메시지를 온전히 수신하는지 확인한다.

---

### Story S-3: SSE 스트림 무중단 자동 복구

**As a** 김민수 (Minsu Kim),  
**I want** 모니터링 중 네트워크 장애 등으로 SSE 연결이 잠시 끊기거나 화면을 새로고침해도,  
**So that** 직전에 보았던 로그 이후의 누락된 로그만 자동으로 다시 전송받아 끊김 없는 모니터링 경험을 누리고 싶다.

#### Acceptance Criteria
- **Given**: 민수의 브라우저 연결이 일시 중단된 사이 서버가 5개의 로그 이벤트를 추가로 발행했고,
- **When**: 민수의 클라이언트가 이전에 수신한 마지막 이벤트 ID를 헤더(`Last-Event-ID: {event_id}`)에 싣고 SSE 연결을 재시도할 때,
- **Then**: 
  - 서버는 `Last-Event-ID`를 파싱하여 PostgreSQL DB의 `event_logs` 테이블에서 해당 ID 초과의 로그만 정렬 조회한다.
  - 해당 누락 로그들을 새로운 SSE 스트림 시작 시점에 즉시 순차 전송(Catch-up)한 뒤, 현재 실행 중인 실시간 로그를 계속 이어서 스트리밍한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration
- **Required Test Evidence**: `test_sse_catchup`에서 `Last-Event-ID` 헤더를 포함해 GET 요청을 전송했을 때, 응답 스트림의 시작부에 DB에 누적되었던 미수신 이벤트들이 재전송되는지 검증한다.

---

### Story S-4: Artifact 미리보기 및 다운로드

**As a** 김민수 (Minsu Kim),  
**I want** 설계 완료 후 생성된 3D 렌더링 이미지와 STL 3D 모델링 파일을 다운로드받고 싶다,  
**So that** 3D 프린터 출력 전에 설계 형상을 시각적으로 확인하고 실제 출력을 진행하고 싶다.

#### Acceptance Criteria
- **Given**: Job 상태가 성공(`COMPLETED`)으로 전이되고, Workspace 내부에 `preview.png`와 `output.stl`이 생성되었을 때,
- **When**: 민수가 Artifact 다운로드 링크를 요청하거나 다운로드 API를 호출할 때,
- **Then**:
  - `StorageService` 추상화를 거쳐 로컬 파일 시스템 내 저장된 바이너리 파일을 다운로드 응답(바이트 스트림)으로 제공한다.
  - 민수가 허용되지 않은 Workspace 외부 파일(예: OS 민감 파일)을 요청할 경우 권한 에러(403 Forbidden)를 반환한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration
- **Required Test Evidence**: `test_artifact_download`에서 지정된 Job ID의 `preview.png`를 요청하여 파일 바이트가 온전히 반환되는지 확인하고, `/api/v1/artifacts/../../etc/passwd`와 같은 경로 요청 시 403 Forbidden 에러가 발생하는지 확인한다.

---

### Story S-5: 대화형 피드백을 통한 설계 반복 수정

**As a** 김민수 (Minsu Kim),  
**I want** 생성된 3D 결과물을 보고 "오른쪽 벽면에 케이블 통과 구멍을 5mm 지름으로 뚫어줘" 같이 자연어로 수정 피드백을 입력하고 싶다,  
**So that** 이전에 작성된 OpenSCAD 코드(`model.scad`)를 바탕으로 LLM이 도면을 점진적으로 수정 및 재렌더링하여 완성도를 높여가기를 원한다.

#### Acceptance Criteria
- **Given**: 완료된 이전 Job(예: `Job #1`)의 결과인 `model.scad`와 `design-spec.md`가 존재할 때,
- **When**: 민수가 해당 Job ID를 참조하여 추가 수정 프롬프트를 전송할 때,
- **Then**:
  - 서버는 새 Job(예: `Job #2`)을 생성하고 이전 Job의 Workspace 파일들을 새 Workspace로 복사하여 컨텍스트를 유지한다.
  - LLM 호출 시 이전 `model.scad` 및 피드백 프롬프트를 함께 주입하여 수정 계획(Action Plan)을 받아온 뒤 검증 실행한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration
- **Required Test Evidence**: `test_iterative_design`에서 이전 Job ID와 피드백 프롬프트를 기반으로 신규 Job을 생성했을 때, 이전 `model.scad` 파일 내용이 복사되어 존재하고 LLM 프롬프트에 포함되어 동작하는지 시뮬레이션 검증한다.

---

## 2. 백엔드 기능 기준 스토리 (Feature-Based Stories)

### Story S-6: LLM Action Plan 파싱 및 유효성 검증

**As a** 플랫폼 시스템 아키텍트,  
**I want** LLM이 생성한 JSON Action Plan의 경로 및 액션 구조를 엄격히 검증하고 싶다,  
**So that** LLM이 직접 쉘 커맨드를 주입하거나 Job Workspace를 탈출하여 호스트 시스템 파일을 오염시키는 위협을 원천 차단하고 싶다.

#### Acceptance Criteria
- **Given**: LLM으로부터 작업 계획 JSON(예: `[{"action": "WRITE_FILE", "path": "model.scad", "content": "..."}]`)을 전달받았을 때,
- **When**: 서버가 해당 Plan을 파싱 및 유효성 검사할 때,
- **Then**:
  - 정의된 4가지 액션(`CREATE_DIRECTORY`, `WRITE_FILE`, `RUN_TOOL`, `CREATE_ARTIFACT`)만 허용한다.
  - 대상 파일 경로(`path`)에 `../`, 절대 경로, 심볼릭 링크 등 상위 디렉토리 탈출 시도가 단 하나라도 감지될 경우 예외를 발생시키고 실행을 중단하며 Job을 즉시 `FAILED` 처리한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit
- **Required Test Evidence**: `test_plan_security_validation`에서 악성 경로(`../../config.env`, `/var/log`)가 포함된 JSON Plan을 파서에 주입하여 예외가 정상적으로 던져지는지 검증하는 단위 테스트 작성.

---

### Story S-7: 리소스 제약이 적용된 OpenSCAD CLI 실행 격리

**As a** 플랫폼 시스템 아키텍트,  
**I want** OpenSCAD CLI 실행 시 OS 수준의 엄격한 자원 제약을 부과하고 싶다,  
**So that** 잘못된 3D 렌더링 코드(예: 무한 루프 렌더링)에 의해 전체 API 서버의 CPU, 메모리가 고갈되거나 디스크 용량이 초과되는 장애를 예방하고 싶다.

#### Acceptance Criteria
- **Given**: `RUN_TOOL` 액션으로 OpenSCAD CLI를 실행할 때,
- **When**: 백엔드 Runner가 OS 프로세스를 생성할 때 (FastAPI 백그라운드 태스크 내부),
- **Then**:
  - `subprocess.run` 호출 시 쉘 확장 없이 인수 리스트(`["openscad", "-o", "preview.png", "model.scad"]`) 형태로 호출하여 커맨드 인젝션을 차단한다.
  - 최대 실행 시간 타임아웃(예: 30초)을 설정하고 이를 초과할 시 즉시 프로세스를 강제 종료(Kill) 처리한다.
  - 디스크 공간 고갈 방지를 위해 산출할 수 있는 파일의 최대 크기를 시스템 수준에서 제한한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration/performance
- **Required Test Evidence**: `test_openscad_timeout`에서 30초 이상 실행되는 무한 렌더링 scad 파일을 인위적으로 인입시킨 뒤, 30초 뒤에 `TimeoutExpired` 예외가 발생하며 OS 프로세스가 해제되는지 검증한다.

---

## 3. R-16 Artifact ID 기반 보안 다운로드 스토리

### Story S-8: Artifact ID로 생성 결과물 안전하게 다운로드

**As a** 김민수(최종 사용자),  
**I want** 서버 경로나 파일명을 직접 제공하지 않고 `artifact_id` 기반 링크로 생성 결과물을 다운로드하고 싶다,  
**So that** 변조된 경로로부터 보호받으면서 원래 파일명과 미디어 타입이 유지된 결과물을 안전하게 사용할 수 있다.

#### Acceptance Criteria

##### 시나리오 1: 안전한 Artifact 등록
- **Given** 소유 Job의 workspace root 안에 일반 파일이 존재하고 등록할 `relative_path`가 유효한 상대경로일 때,
- **When** Artifact 등록 주체가 해당 파일을 Artifact로 등록하면,
- **Then** 서비스는 workspace root 기준 경로를 검증하고 `id`, `job_id`, `relative_path`, `filename`, `content_type` 메타데이터를 영속화한다.
- **And** 절대경로, 빈 경로, `.`, `..`, `../` segment 또는 플랫폼별 동등 경로 segment가 포함되면 메타데이터 영속화 전에 거부한다.

##### 시나리오 2: Artifact ID 기반 다운로드 성공
- **Given** DB에 유효한 Artifact 메타데이터가 있고 연결된 소유 Job workspace root 내부에 일반 파일이 존재할 때,
- **When** 민수의 클라이언트가 `GET /api/v1/artifacts/{artifact_id}/download`를 호출하면,
- **Then** 서비스는 `artifact_id`만으로 메타데이터와 소유 Job workspace root를 조회한다.
- **And** 등록 시점 검증을 신뢰하지 않고 `Path.resolve()`와 `Path.is_relative_to()` 또는 안전한 동등 헬퍼로 물리 경로를 다시 검증한다.
- **And** HTTP 200 파일 응답은 Artifact의 `content_type`을 `Content-Type`으로, Artifact의 `filename`을 `Content-Disposition` 다운로드 filename으로 제공한다.

##### 시나리오 3: 경로 공격 차단
- **Given** DB 메타데이터가 변조되었거나 레거시 데이터가 traversal, 절대경로 또는 workspace와 공통 문자열 접두사만 가진 형제 경로를 가리킬 때,
- **When** 다운로드 서비스가 대상 경로를 다시 해석하면,
- **Then** `../` traversal, 절대경로 및 prefix-bypass를 HTTP 403으로 차단한다.
- **And** 문자열 `startswith`만으로 경로 경계를 판단하지 않는다.
- **And** 사용자 응답에는 workspace root나 대상 파일의 절대 서버 경로를 포함하지 않는다.

##### 시나리오 4: 찾을 수 없는 Artifact
- **Given** `artifact_id`가 DB에 없거나, DB 메타데이터는 있지만 물리 파일이 없거나, 대상이 일반 파일이 아닐 때,
- **When** 다운로드 API가 호출되면,
- **Then** HTTP 404를 반환한다.
- **And** 사용자 응답에는 절대 서버 경로를 포함하지 않는다.

##### 시나리오 5: 향후 권한 검사 확장성
- **Given** R-16에서는 인증·인가가 구현 범위 밖일 때,
- **When** Artifact 조회와 다운로드 결정 흐름을 구성하면,
- **Then** 라우터가 아닌 `ArtifactService` 내부에 추후 소유권 또는 권한 검사를 삽입할 수 있는 구조를 유지한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration/contract/security
- **Required Test Evidence**:
  - 서비스 단위 테스트로 정상 상대경로 등록과 절대경로, 빈 경로, `.`, `..`, `../` segment 거부를 검증한다.
  - API 통합 테스트로 성공 다운로드의 파일 바이트, `Content-Type`, `Content-Disposition` filename을 검증한다.
  - 알 수 없는 `artifact_id`, 누락 파일, 일반 파일이 아닌 대상이 각각 HTTP 404인지 검증한다.
  - DB에 주입된 traversal, 절대경로, prefix-bypass 메타데이터가 각각 HTTP 403인지 검증한다.
  - 모든 실패 응답에 절대 서버 경로가 포함되지 않는지 검증한다.
  - 전체 기존 테스트 스위트의 회귀가 없는지 검증한다.

#### INVEST 검증
- **Independent**: 기존 Job 생성·SSE 흐름과 독립적으로 Artifact 등록 및 다운로드 계약을 검증할 수 있다.
- **Negotiable**: 내부 파일 배치 방식은 변경할 수 있으나 ID 전용 API와 보안·HTTP 계약은 유지한다.
- **Valuable**: 최종 사용자가 생성 결과물을 안전하고 예측 가능한 방식으로 받는다.
- **Estimable**: Artifact 모델, 서비스, 라우터, 마이그레이션 및 제한된 테스트 범위로 산정할 수 있다.
- **Small**: 단일 다운로드 사용자 여정과 그 선행 등록 경계로 제한된다.
- **Testable**: 정상 응답, 헤더, 403, 404 및 경로 검증을 자동화할 수 있다.

#### 추적성
- **Requirement**: R-16
- **Primary Persona**: R16-P1 김민수
- **Supporting Persona**: R16-P2 API 클라이언트 개발자
- **Supporting Actor**: R16-A1 Artifact 등록 주체
- **Implementation Verification Target**: Artifact 등록 서비스 단위 테스트와 다운로드 API 통합·보안 테스트
