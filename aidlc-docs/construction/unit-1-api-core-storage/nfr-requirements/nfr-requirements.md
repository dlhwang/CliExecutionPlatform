# 비기능 요구사항 정의서 (NFR Requirements) - Unit 1: API Core & Storage Service

본 문서는 **Unit 1: API Core & Storage Service**에 적용될 성능(Latency), 자원 관리(Cleanup), 속도 제한(Rate Limiting) 및 보안 비기능 요구사항을 상세히 명세합니다.

---

## 1. 성능 및 지연시간 요구사항 (Performance & Latency)

* **API 응답 속도 (Latency Target)**:
  * **대상 API**: `POST /api/v1/jobs` (Job 등록 API)
  * **성능 목표**: P95 기준 **500ms 이하**의 응답 속도를 보장합니다.
  * **기술적 고려사항**: Job 정보의 데이터베이스 저장 및 물리 디렉토리(`.workspaces/jobs/{job_id}/`, `.workspaces/artifacts/{job_id}/`) 생성을 동기적으로 처리하므로, 디스크 I/O 블로킹 대기시간을 감안하여 500ms 기준을 만족하도록 설계합니다. 실제 무거운 작업(LLM 플래닝 및 OpenSCAD 렌더링)은 비동기로 백그라운드 태스크에 위임하여 동기 응답 속도에 영향을 주지 않도록 합니다.

---

## 2. 자원 관리 및 데이터 정리 정책 (Resource Cleanup Policy)

* **임시 작업 공간 정리**:
  * **대상 디렉토리**: `.workspaces/jobs/{job_id}/` (로컬 디바이스 임시 공간)
  * **처리 시점**: 작업이 성공적으로 완료(`COMPLETED`)되거나 또는 처리 도중 예외가 발생하여 실패(`FAILED`)한 **즉시** 정리 프로세스를 가동합니다.
  * **동작 방식**: 
    * 성공 시: 아티팩트 보관소(`.workspaces/artifacts/{job_id}/`)로 최종 빌드 산출물 복사 작업을 선행합니다.
    * 공통: 임시 디렉토리 하위의 모든 작업 파일 및 폴더를 재귀적으로 강제 삭제합니다.
  * **목적**: 동시 다발적인 Job 실행으로 인한 호스트 OS의 디스크 공간(Disk Space) 부족 장애를 사전에 차단하고 불필요한 파일 유출을 방지합니다.

---

## 3. 보안 및 서비스 안정성 요구사항 (Security & Rate Limiting)

* **경로 조작 공격 차단 (Directory Traversal Prevention)**:
  * **요구 사항**: 모든 파일 작업(`write_file`, `read_file`, `get_artifact_path` 등) 시, 사용자의 악의적인 상위 디렉토리 침투 및 탈출 시도를 완벽히 격리해야 합니다.
  * **세부 규칙**:
    * 경로 문자열 내 `../` 또는 `..\\` 탐지 시 예외 발생.
    * `Path.resolve()`를 통해 구한 절대 경로가 해당 Job 전용 디렉토리(`.workspaces/jobs/{job_id}/` 또는 `.workspaces/artifacts/{job_id}/`) 내부의 하위 경로로 종속되어 있는지 검증합니다.

* **API 속도 제한 (Rate Limiting)**:
  * **대상 API**: `POST /api/v1/jobs` (신규 Job 생성)
  * **제한 수준**: **단일 IP당 분당 최대 10회(10 requests/min)**의 호출 허용을 제한 정책으로 탑재합니다.
  * **목적**: 무제한적인 API 호출로 인해 값비싼 외부 LLM API(Gemini, OpenAI 등) 호출 비용이 폭증하는 것을 차단하고, OpenSCAD CLI 백그라운드 프로세스가 CPU/메모리 자원을 과다 점유하여 서버 전체가 다운되는 현상(DoS 공격 및 리소스 고갈)을 예방합니다.
