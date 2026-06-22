# 빌드 및 테스트 요약 (Build and Test Summary)
# CLI Execution Platform - Backend MVP

> 실행 일시: 2026-06-19T17:41:45+09:00  
> 실행 명령: `python -m pytest tests/ -v`  

## 개요

본 문서는 LLM 기반 Workspace CLI Execution Platform 백엔드 MVP에 대한 최종 빌드 및 통합 검증 보고서입니다.
5대 핵심 유닛(Core API, Parser/Validator, CLI Runner, SSE Streaming, Iterative Refinement Orchestrator) 및 R-10 핫픽스(LLM 프롬프트 스키마 명세화 및 오케스트레이션 에러 상세 기록)의 전체 소스 코드 구현 및 단위/통합/시나리오 테스트 자동화 검증이 성공적으로 완료되었습니다.

## 검증된 범위

| Unit | 테스트 파일 | 테스트 수 | 통과 | 실패 | 상태 |
|---|---|---:|---:|---:|---|
| Unit 1: API Core & Storage Service | `test_unit_1.py` | 4 | 4 | 0 | ✅ PASS |
| Unit 2: Parser & Policy Validator Service | `test_unit_2.py` | 5 | 5 | 0 | ✅ PASS |
| Unit 3: CLI Runner Service | `test_unit_3.py` | 8 | 8 | 0 | ✅ PASS |
| Unit 4: SSE Streaming & Event Catch-up | `test_unit_4.py` | 16 | 16 | 0 | ✅ PASS |
| Unit 5: Iterative Refinement Orchestrator | `test_unit_5.py` | 15 | 15 | 0 | ✅ PASS |
| **합계** | | **48** | **48** | **0** | ✅ **ALL PASS** |

## 핵심 비즈니스 시나리오 및 NFR 검증 요약

- **S-1 & S-4 (Job / Storage)**: UUIDv7 기반 Job 식별자 발급, `CREATED -> RUNNING -> COMPLETED/FAILED` 상태 전이, Workspace 디렉토리 생성 및 `../` 경로를 통한 디렉토리 Traversal 보안 공격 차단, 생성 완료 아티팩트 다운로드 및 유효성 검증 완료.
- **S-6 (Parser / Validator)**: LLM이 생성한 마크다운 코드블록 및 Fallback JSON 추출, Pydantic DTO 스키마 유효성 및 보안 정책(인가되지 않은 CLI 명령어 차단, 절대경로/심볼릭링크 등 우회 경로 차단) 선검증 완료.
- **US-3-1 & Q2 (CLI Execution)**: OpenSCAD CLI 안전 실행, 특수문자를 이용한 OS Command Injection 방어 인자 Allowlist 검사, 타임아웃(30초) 강제 종료 및 부분 실행 결과 EventLog DB 기록 보존 검증 완료.
- **Unit 4 (SSE Streaming)**: SSE 통신 토큰 검증, 분실된 실시간 이벤트를 복원하는 `Last-Event-ID` 기반의 Catch-up 메커니즘, 10분 초과 세션 재연결, 최대 동시 커넥션(20개) 제한 및 DB 일시 장애 지수 백오프 재시도 검증 완료.
- **Unit 5 (Orchestration & Refinement)**: 완료된 부모 Job에 기반한 refinement API 및 자식 Job 연동, Workspace 컨텍스트 상속(최대 5MB 제한), 120초 LLM 요청 타임아웃 및 최대 2회 재시도, 프로세스 로컬 동시 2개 작업 제한(Semaphore) 및 10분 wait timeout, 15분 경과 stale RUNNING Job 자동 실패 복구(lifespan) 검증 완료.
- **KST DB 타임존 (R-8)**: PostgreSQL 연결 시 `connect_args`를 통해 타임존을 `Asia/Seoul`로 주입하고, SQLite 로컬 개발/테스트 환경에서 예외 없이 안전하게 통과됨을 입증함.
- **OpenAI 호환 페이로드 (R-9)**: `chat/completions` endpoint를 자동으로 감지하여 표준 OpenAI `messages` 페이로드로 가공해 호출하고 `choices` 응답 구조를 파싱하는 신규 비동기 테스트 케이스(`test_llm_client_openai_format`) 통과.
- **LLM Plan Schema 명세화 (R-10)**: `llm/client.py` 시스템 프롬프트에 각 액션의 정확한 JSON 필드명(`tool_name`, `args` 등) 및 예시를 명시하여, LLM이 Pydantic DTO에 호환되지 않는 필드명을 생성하는 문제를 원천 차단. `test_llm_client_system_prompt_contains_schema` 통과.
- **오케스트레이션 에러 상세 기록 (R-10)**: `orchestrator/service.py` ORCHESTRATION_FAILED 이벤트에 `Detail: {str(exc)}` 추가하여 SSE 로그 및 DB에서 오류 원인 즉시 파악 가능. `test_orchestration_failed_log_includes_exception_detail` 통과.

## 요구사항 검증 매핑 (R-10)

| 요구사항 | 검증 테스트 | 결과 |
|---|---|---|
| R-10: 시스템 프롬프트 스키마 명세 | `test_llm_client_system_prompt_contains_schema` | ✅ PASS |
| R-10: 오케스트레이션 에러 상세 로그 | `test_orchestration_failed_log_includes_exception_detail` | ✅ PASS |
| 회귀 방지 (전체) | `pytest tests/` 전체 실행 | ✅ 48/48 PASS |

## 현재 전체 상태

| 항목 | 상태 |
|---|---|
| 전체 빌드 및 컴파일 | 성공 (FastAPI, SQLAlchemy) |
| 전체 테스트 통과율 | 100% (48/48 passed) |
| 미해결 회귀 오류 | 없음 |
| Operations 진행 준비 | **Yes** |

## 결론 및 권장 사항

1. 백엔드 핵심 기능 및 비기능(NFR) 요구사항의 로컬 빌드 및 테스트는 100% 통과했습니다.
2. R-10 핫픽스(시스템 프롬프트 스키마 명세화, 에러 상세 기록)가 적용되어 LLMPlanValidationError 유형의 오류가 예방되고 SSE 로그에서 즉시 원인 파악이 가능해졌습니다.
3. 수동 검증 대상(예: 실제 AWS S3 및 외부 PostgreSQL 연동, 실제 외부 LLM 호출)은 스테이징 배포 인프라 구성 시 환경변수 교체 후 통합 점검을 권장합니다.
4. 본 빌드 및 검증 문서를 토대로 **Operations Phase (배포 및 운영 계획 수립)**로 진행을 허가합니다.

---

# R-13 Build and Test Summary

## 실행 정보

- **실행 시각**: 2026-06-22T10:14:28+09:00
- **Python build**: Pass (`py_compile`)
- **전체 테스트**: 56 passed, 0 failed
- **Docker build/smoke**: N/A - 현재 환경에 Docker CLI와 설치된 WSL 배포판이 없음

## R-13 요구사항 검증

| 요구사항 | 자동화 증거 | 명령 | 결과 |
| --- | --- | --- | --- |
| Job workspace를 CLI `cwd`로 사용 | `test_run_tool_uses_job_workspace_as_cwd` | 전체 pytest | Pass |
| Workspace 부재 시 실행 전 차단 | `test_run_tool_rejects_missing_job_workspace` | 전체 pytest | Pass |
| 서버 ERROR traceback | `test_orchestration_failed_log_includes_exception_detail` | 전체 pytest | Pass |
| EventLog 전이 실패도 서버 기록 | `test_orchestration_transition_failure_is_logged` | 전체 pytest | Pass |
| Linux/OpenSCAD/Xvfb 이미지 정의 | `test_dockerfile_packages_openscad_and_runs_as_non_root` | 전체 pytest | Pass (정적) |
| Headless wrapper 인자 안전 전달 | `test_headless_wrapper_forwards_arguments_without_eval` | 전체 pytest | Pass (정적) |
| `.env`와 workspace build 제외 | `test_dockerignore_excludes_secrets_and_runtime_data` | 전체 pytest | Pass (정적) |
| Compose 앱 단일 service 및 외부 DB | `test_compose_defines_only_the_application_service` | 전체 pytest | Pass (정적) |
| `.env.sample` ASCII-only | `test_env_sample_remains_ascii_only` | 전체 pytest | Pass |
| Compose build 및 실제 STL/PNG | Container smoke | `docker compose build` 및 OpenSCAD 실행 | N/A |
| 기존 API/SSE 회귀 | 전체 56 tests | `python -m pytest -q` | Pass |

## 결과 분류

- **Unit/Regression**: Pass
- **Python compile**: Pass
- **Static deployment/security**: Pass
- **Container build**: N/A
- **Actual OpenSCAD STL/PNG in container**: N/A
- **External PostgreSQL container integration**: N/A

## N/A 사유와 필수 후속 검증

현재 Windows 환경에는 `docker` command가 없고 WSL에는 설치된 Linux 배포판이 없다. 다음 명령은 WSL2/Linux Docker 환경에서 반드시 실행해야 한다.

```bash
docker compose config
docker compose build
docker compose run --rm app /usr/local/bin/openscad-headless --version
docker compose up -d
docker compose ps
```

## 전체 상태

- **코드 회귀 및 정적 요구사항 검증**: Complete
- **실제 container acceptance 검증**: Incomplete
- **로컬 코드 통합 준비**: Yes
- **운영 배포 준비**: Conditional - Docker build, 외부 DB 연결 및 STL/PNG smoke 통과 필요

---

# R-14 Build and Test Summary

## 실행 정보

- **실행 시각**: 2026-06-22T13:55:00+09:00
- **Python build**: Pass (`py_compile`)
- **전체 테스트**: 58 passed, 0 failed
- **Docker build/smoke**: N/A - 컨테이너 로컬 실행 환경(Docker CLI)이 없음

## R-14 요구사항 검증

| 요구사항 | 자동화 증거 | 명령 | 결과 |
| --- | --- | --- | --- |
| 격리 실행 중 하위 경로 결과물 생성 | `test_run_tool_with_subdirectory_output_success` | 전체 pytest | Pass |
| 격리 실행 중 Path Traversal 방어 | `test_run_tool_with_traversal_output_fails` | 전체 pytest | Pass |
| db 서비스 compose 통합 대응 검증 | `test_compose_defines_expected_services` | 전체 pytest | Pass |
| 기존 API/SSE 회귀 | 전체 58 tests | `python -m pytest` | Pass |

## 결과 분류

- **Unit/Regression**: Pass
- **Python compile**: Pass
- **Static deployment/security**: Pass
- **Container build**: N/A

## 전체 상태

- **코드 회귀 및 정적 요구사항 검증**: Complete
- **실제 container acceptance 검증**: Incomplete (Docker 미설치 환경)
- **로컬 코드 통합 준비**: Yes
- **운영 배포 준비**: Conditional - Docker 환경에서 build 및 STL/PNG smoke 통과 필요

---

# R-15 Build and Test Summary (Refinement Feedback 보완 추가 포함)

## 실행 정보

- **실행 시각**: 2026-06-22T14:44:00+09:00
- **Python build**: Pass (`py_compile`)
- **전체 테스트**: 71 passed, 0 failed
- **Docker build/smoke**: N/A - 컨테이너 로컬 실행 환경(Docker CLI)이 없음

## R-15 요구사항 검증

| 요구사항 | 자동화 증거 | 명령 | 결과 |
| --- | --- | --- | --- |
| 마크다운 펜스 및 prose 검사 | `test_scad_static_validation_rejects_markdown_fence`<br>`test_scad_validation_feedback_does_not_include_full_content` | 전체 pytest | Pass |
| 벡터 property access 차단 | `test_scad_static_validation_rejects_vector_property_access` | 전체 pytest | Pass |
| 싱글 쿼트 문자 사용 차단 | `test_scad_static_validation_rejects_single_quotes` | 전체 pytest | Pass |
| Radian conversion 사용 차단 | `test_scad_static_validation_rejects_180_div_pi`<br>`test_scad_static_validation_rejects_pi_div_180` | 전체 pytest | Pass |
| 빈 파일 및 키워드 누락 차단 | `test_scad_static_validation_rejects_empty_file`<br>`test_scad_static_validation_rejects_missing_scad_keyword` | 전체 pytest | Pass |
| [보완] 피드백 크기 제한 (1,500자) | `test_scad_validation_feedback_is_bounded` (길이 및 요약 문구 검증) | 전체 pytest | Pass |
| [보완] snippet 길이 제한 (150자) | `test_scad_validation_feedback_is_bounded` (truncate '...' 검증) | 전체 pytest | Pass |
| [보완] 원본 전체 포함 차단 | `test_scad_validation_feedback_does_not_include_full_content` | 전체 pytest | Pass |
| [보완] shutil.copyfile() 교체 | `tests/test_unit_2.py`, `tests/test_unit_3.py` (간접 통과) | 전체 pytest | Pass |
| 기존 API/SSE 및 Refinement 회귀 | 전체 71 tests | `python -m pytest` | Pass |

## 전체 상태

- **코드 회귀 및 정적 요구사항 검증**: Complete (71/71 tests passed)
- **실제 container acceptance 검증**: Incomplete (Docker 미설치 환경)
- **운영 배포 준비**: Conditional - Docker 환경에서 build 및 STL/PNG smoke 통과 필요


