# 이전 실행 계획 - Hotfix R-12 (R-13 우선 처리로 일시 중지)

> 현재 활성 실행 계획은 이 문서 하단의 **Hotfix R-13 (Linux/WSL2 및 Docker Compose 표준화)**입니다.

## 상세 분석 요약

### 변경 범위
- **변경 유형**: 브라운필드 설정 템플릿 및 문서 핫픽스
- **주요 변경**: `.env.sample`을 ASCII-only 템플릿으로 변경하고 사용 규칙을 문서화
- **관련 파일**: `.env.sample`, `README.md`, 신규 정적 검증 테스트

### 영향 평가
- **사용자 화면/API 변경**: 없음
- **런타임 코드 변경**: 없음
- **데이터 모델 변경**: 없음
- **환경 설정 정책 변경**: 있음 - `.env`의 주석과 값은 ASCII 문자만 사용
- **비기능 영향**: Windows CP949 환경에서 SlowAPI 시작 오류 재발 가능성 감소

### 컴포넌트 관계
- **템플릿**: `.env.sample`이 실제 `.env` 생성의 기준
- **안내 문서**: `README.md`가 ASCII-only 제약과 원인을 설명
- **검증**: 자동화 테스트가 `.env.sample`의 ASCII 호환성을 지속적으로 확인
- **제외 범위**: `database.py`, `limiter.py`, `requirements.txt` 및 실제 `.env`

### 위험 평가
- **위험 수준**: 낮음
- **롤백 복잡도**: 쉬움
- **테스트 복잡도**: 단순
- **잔여 위험**: 사용자가 실제 `.env`에 비ASCII 문자를 직접 추가하면 동일 오류가 재발할 수 있음

## 워크플로 시각화

```mermaid
flowchart TD
    Start(["R-12 환경 파일 인코딩 오류"])
    WD["Workspace Detection<br/><b>COMPLETED</b>"]
    RE["Reverse Engineering<br/><b>SKIP</b>"]
    RA["Requirements Analysis<br/><b>UPDATED</b>"]
    US["User Stories<br/><b>SKIP</b>"]
    WP["Workflow Planning<br/><b>APPROVED</b>"]
    AD["Application Design<br/><b>SKIP</b>"]
    UG["Units Generation<br/><b>SKIP</b>"]
    FD["Functional Design<br/><b>SKIP</b>"]
    NFRA["NFR Requirements<br/><b>SKIP</b>"]
    NFRD["NFR Design<br/><b>SKIP</b>"]
    ID["Infrastructure Design<br/><b>SKIP</b>"]
    CG["Code Generation<br/><b>EXECUTE</b>"]
    BT["Build and Test<br/><b>EXECUTE</b>"]
    OPS["Operations<br/><b>PLACEHOLDER</b>"]
    End(["R-12 완료"])

    Start --> WD --> RE --> RA --> US --> WP
    WP --> AD --> UG --> FD --> NFRA --> NFRD --> ID --> CG
    CG --> BT --> OPS --> End

    style WD fill:#4CAF50,stroke:#1B5E20,stroke-width:3px,color:#fff
    style RA fill:#4CAF50,stroke:#1B5E20,stroke-width:3px,color:#fff
    style WP fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style CG fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style BT fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style RE fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style US fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style AD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style UG fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style FD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style NFRA fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style NFRD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style ID fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style OPS fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style Start fill:#CE93D8,stroke:#6A1B9A,stroke-width:3px,color:#000
    style End fill:#CE93D8,stroke:#6A1B9A,stroke-width:3px,color:#000
    linkStyle default stroke:#333,stroke-width:2px
```

### 텍스트 대체 표현

1. Workspace Detection 완료
2. Reverse Engineering 생략
3. Requirements Analysis 정책 변경 반영
4. User Stories 생략
5. Workflow Planning 승인 완료
6. Application Design, Units Generation 및 Construction 설계 단계 생략
7. Code Generation에서 템플릿, 문서, 정적 검증 테스트 변경
8. Build and Test에서 정적 검증 및 전체 회귀 수행
9. Operations는 Placeholder로 종료

## 단계 계획

### INCEPTION PHASE
- [x] Workspace Detection - 완료
- [x] Reverse Engineering - 생략: 기존 구조가 명확한 단순 핫픽스
- [x] Requirements Analysis - 사용자 정책 변경 반영
- [x] User Stories - 생략: 사용자 흐름이나 API 동작 변화 없음
- [x] Workflow Planning - 변경 계획 승인 완료
- [x] Application Design - 생략: 신규 컴포넌트나 서비스 없음
- [x] Units Generation - 생략: 단일 문서·템플릿 변경

### CONSTRUCTION PHASE
- [x] Functional Design - 생략: 신규 비즈니스 로직 없음
- [x] NFR Requirements - 생략: ASCII 호환성 정책으로 범위 확정
- [x] NFR Design - 생략: 별도 설계 패턴 불필요
- [x] Infrastructure Design - 생략: 배포 및 인프라 변경 없음
- [ ] Code Generation - 실행
- [ ] Build and Test - 실행

### OPERATIONS PHASE
- [ ] Operations - Placeholder

## 변경 순서

1. `.env.sample`: 모든 주석과 예시 값을 ASCII로 변환
2. `README.md`: 실제 `.env`의 ASCII-only 정책과 Windows/SlowAPI 제약 안내
3. 테스트: `.env.sample`의 ASCII 호환성을 검증하는 정적 테스트 추가

## 요구사항 검증 계획

| 요구사항 | 인수 기준 | 필수 테스트 증거 | 테스트 수준 | 예정 파일 또는 시나리오 | 필요 결과 |
| --- | --- | --- | --- | --- | --- |
| R-12 | `.env.sample` 전체가 ASCII | 원시 바이트의 ASCII 디코딩 성공 | unit/static | 신규 환경 템플릿 테스트 | Pass |
| R-12 | README에 제약 명시 | 문서에 ASCII-only 및 Windows/SlowAPI 원인 포함 | static/manual review | `README.md` 검토 | Pass |
| R-12 | 런타임 코드 미변경 | 관련 소스 diff 없음 | static | `database.py`, `limiter.py`, `requirements.txt` diff 확인 | Pass |
| 회귀 방지 | 기존 동작 유지 | 전체 테스트 실행 | integration | `pytest -q` | 모든 테스트 통과 |

## 예상 규모
- **실행 단계**: Code Generation, Build and Test
- **생략 단계**: Reverse Engineering, User Stories, Application Design, Units Generation, Functional Design, NFR Requirements, NFR Design, Infrastructure Design
- **작업 규모**: 소규모 템플릿·문서 핫픽스

## 성공 기준
- `.env.sample`에 비ASCII 문자가 없다.
- README가 실제 `.env`에도 같은 정책을 적용하도록 명확히 안내한다.
- 자동화 테스트가 템플릿의 비ASCII 문자 재도입을 차단한다.
- 런타임 코드와 의존성은 변경하지 않는다.
- 전체 회귀 테스트가 통과한다.

---

# 실행 계획 - Hotfix R-13 (Linux/WSL2 및 Docker Compose 표준화)

## 상세 분석 요약

### 변경 범위
- **변경 유형**: 브라운필드 런타임 제약 변경, 배포 구성 추가 및 실행 장애 수정
- **주요 변경**: Linux 전용 서버 실행, Windows 로컬 개발의 WSL2 제한, OpenSCAD 포함 Docker 이미지와 Docker Compose 구성, CLI workspace 기준 실행, 서버 traceback 기록
- **관련 컴포넌트**: CLI Runner, Orchestrator, 환경 설정, Docker 배포 구성, 개발·운영 문서, 테스트
- **데이터베이스**: 기존 외부 DB를 `DATABASE_URL`로 연결하며 Compose에 DB 서비스는 추가하지 않음

### 영향 평가
- **사용자 화면 변경**: 없음
- **API 계약 변경**: 없음
- **데이터 모델 변경**: 없음
- **구조 변경**: Docker Compose 기반 배포 단위와 영속 workspace volume 추가
- **런타임 변경**: 네이티브 Windows 지원 제외, Linux/WSL2/Docker만 지원
- **비기능 영향**: 배포 재현성, 장애 관측성, 비밀정보 처리 및 workspace 영속성 개선

### 컴포넌트 관계
- **Docker Compose**: 애플리케이션 컨테이너의 환경 변수, 포트, volume, healthcheck를 조정
- **Docker 이미지**: Python 애플리케이션과 Linux OpenSCAD CLI를 패키징
- **외부 DB**: Compose 외부에서 운영되며 컨테이너가 주입된 `DATABASE_URL`로 접속
- **CLI Runner**: Job workspace를 subprocess working directory로 사용
- **Orchestrator**: 처리된 백그라운드 예외를 EventLog와 서버 ERROR traceback에 기록
- **문서**: WSL2 직접 실행과 Docker Compose 실행 절차 및 지원 범위를 설명

### 위험 평가
- **위험 수준**: 보통
- **롤백 복잡도**: 보통 - Docker 산출물 제거와 두 소스 파일 복구로 가능
- **테스트 복잡도**: 보통 - 단위 테스트, 전체 회귀, 이미지 빌드 및 컨테이너 smoke test 필요
- **주요 위험**: OpenSCAD Linux 패키지 및 headless 렌더링, 외부 DB 네트워크 도달성, volume 권한

## 워크플로 시각화

```mermaid
flowchart TD
    Start(["R-13 실행 환경 변경"])
    WD["Workspace Detection<br/><b>COMPLETED</b>"]
    RE["Reverse Engineering<br/><b>SKIP</b>"]
    RA["Requirements Analysis<br/><b>COMPLETED</b>"]
    US["User Stories<br/><b>SKIP</b>"]
    WP["Workflow Planning<br/><b>COMPLETED</b>"]
    AD["Application Design<br/><b>SKIP</b>"]
    UG["Units Generation<br/><b>SKIP</b>"]
    FD["Functional Design<br/><b>SKIP</b>"]
    NFRA["NFR Requirements<br/><b>EXECUTE</b>"]
    NFRD["NFR Design<br/><b>EXECUTE</b>"]
    ID["Infrastructure Design<br/><b>EXECUTE</b>"]
    CG["Code Generation<br/><b>EXECUTE</b>"]
    BT["Build and Test<br/><b>EXECUTE</b>"]
    OPS["Operations<br/><b>PLACEHOLDER</b>"]
    End(["R-13 완료"])

    Start --> WD --> RE --> RA --> US --> WP --> AD --> UG --> FD --> NFRA --> NFRD --> ID --> CG --> BT --> OPS --> End

    style WD fill:#4CAF50,stroke:#1B5E20,stroke-width:3px,color:#fff
    style RA fill:#4CAF50,stroke:#1B5E20,stroke-width:3px,color:#fff
    style WP fill:#4CAF50,stroke:#1B5E20,stroke-width:3px,color:#fff
    style NFRA fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style NFRD fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style ID fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style CG fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style BT fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style RE fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style US fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style AD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style UG fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style FD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style OPS fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style Start fill:#CE93D8,stroke:#6A1B9A,stroke-width:3px,color:#000
    style End fill:#CE93D8,stroke:#6A1B9A,stroke-width:3px,color:#000
    linkStyle default stroke:#333,stroke-width:2px
```

### 텍스트 대체 표현

1. Workspace Detection 완료
2. Reverse Engineering 생략
3. Requirements Analysis 승인 완료
4. User Stories, Application Design, Units Generation, Functional Design 생략
5. NFR Requirements와 NFR Design에서 Linux 컨테이너, 보안 설정, 로깅 및 영속성 기준 확정
6. Infrastructure Design에서 Dockerfile, Docker Compose, volume, 외부 DB 연결 구조 설계
7. Code Generation에서 배포 구성, 런타임 결함, 문서 및 테스트 구현
8. Build and Test에서 단위·회귀·컨테이너 smoke test 수행
9. Operations는 Placeholder로 종료

## 단계 계획

### INCEPTION PHASE
- [x] Workspace Detection - 완료
- [x] Reverse Engineering - 생략: 기존 Unit 3/5 및 애플리케이션 설계 문서 활용
- [x] Requirements Analysis - 승인 완료
- [x] User Stories - 생략: 사용자 기능/API가 아닌 실행·배포 제약 변경
- [x] Workflow Planning - 승인 완료
- [x] Application Design - 생략: 신규 애플리케이션 컴포넌트나 서비스 없음
- [x] Units Generation - 생략: R-13 단일 통합 핫픽스로 순차 구현 가능

### CONSTRUCTION PHASE
- [x] Functional Design - 생략: 신규 비즈니스 규칙이나 데이터 모델 없음
- [x] NFR Requirements - 승인 완료
- [x] NFR Design - 승인 완료
- [x] Infrastructure Design - 승인 완료
- [x] Code Generation - 승인 완료
- [x] Build and Test - 승인 완료: 56 tests 통과, container acceptance N/A

### OPERATIONS PHASE
- [x] Operations - Placeholder 완료

## 변경 순서

1. NFR Requirements: Linux/WSL2 지원 계약과 컨테이너 품질 기준 확정
2. NFR Design: 외부 설정, 비밀정보, 로깅, workspace 영속성 패턴 정의
3. Infrastructure Design: 앱 전용 Docker Compose 서비스와 이미지 구조 설계
4. Docker 배포 구성: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
5. CLI Runner: Job workspace `cwd` 적용
6. Orchestrator: `job_id` 포함 ERROR traceback 로깅
7. 환경·문서: `.env.sample` 및 README의 WSL2/Docker Compose 실행 안내
8. 테스트: 단위 테스트, 전체 회귀, 이미지 빌드 및 Compose smoke test

## 요구사항 검증 계획

| 요구사항 | 인수 기준 | 필수 테스트 증거 | 테스트 수준 | 예정 파일 또는 시나리오 | 필요 결과 |
| --- | --- | --- | --- | --- | --- |
| R-13 | Linux 이미지에 Python 앱과 OpenSCAD 포함 | Compose 이미지 빌드와 OpenSCAD 버전 확인 | container smoke | `docker compose build`, 컨테이너 내 `openscad --version` | Pass |
| R-13 | Compose에 앱 서비스만 존재 | DB 서비스 부재와 외부 `DATABASE_URL` 주입 확인 | static/integration | `docker-compose.yml` 검증 | Pass |
| R-13 | 비밀정보가 이미지에 미포함 | Dockerfile과 Compose에 실제 비밀 값 부재 확인 | static/security | 배포 파일 검사 | Pass |
| R-13 | workspace 영속성 | `.workspaces` volume 연결 확인 | integration | Compose volume 검사 및 재시작 시 파일 유지 | Pass |
| R-13 | CLI가 Job workspace 기준으로 실행 | subprocess `cwd` 인자 검증 | unit | `tests/test_unit_3.py` | Pass |
| R-13 | 서버 traceback 기록 | ERROR 로그에 `job_id`, 예외 타입, traceback 포함 | unit | `tests/test_unit_5.py` | Pass |
| R-13 | 기존 API/SSE 계약 유지 | 전체 테스트 실행 | regression | `pytest -q` | 모든 테스트 통과 |
| R-13 | 실제 CLI 산출물 생성 | 유효한 SCAD 입력을 STL 또는 PNG로 변환 | container smoke | Docker Compose Job 실행 또는 컨테이너 CLI smoke | Pass |

## 성공 기준

- 네이티브 Windows를 지원 범위에서 제외하고 WSL2와 Linux 실행 절차가 명확하다.
- `docker compose up`으로 OpenSCAD 포함 애플리케이션이 시작된다.
- Compose는 DB를 생성하지 않고 기존 외부 DB 연결 정보를 사용한다.
- Job workspace와 artifact가 volume에 보존된다.
- CLI 상대경로가 Job workspace에서 해석된다.
- 오케스트레이션 실패 traceback이 서버 로그에 남는다.
- 전체 테스트와 컨테이너 smoke test가 통과한다.

---

# 실행 계획 - Hotfix R-14 (Docker 격리 실행 시 하위 디렉토리 미생성 및 복사 누락 수정)

## 상세 분석 요약

### 변경 범위
- **변경 유형**: 브라운필드 CLI Runner 실행 격리 로직 버그 수정
- **주요 변경**: `/tmp` 격리 실행 디렉토리 생성 시 workspace의 하위 디렉토리 구조 복제, `args`에 지정된 출력 경로 중 누락된 하위 디렉토리를 `/tmp` 내에 생성, CLI 실행 완료 후 새로 생성된 디렉토리와 파일을 workspace로 재귀 복사.
- **관련 파일**: `runner/service.py`, `tests/test_unit_3.py`

### 영향 평가
- **사용자 화면 변경**: 없음
- **API 계약 변경**: 없음
- **데이터 모델 변경**: 없음
- **구조 변경**: 없음
- **런타임 변경**: 격리 실행 시 하위 디렉토리 생성 및 결과물 재귀 복사
- **비기능 영향**: 안정적인 컨테이너 격리 실행 보장

### 컴포넌트 관계
- **CLI Runner**: `/tmp` 임시 폴더에서 실행하기 전 하위 디렉토리 생성 및 실행 결과물(디렉토리 트리 포함)을 workspace로 복사하는 역할 수행.
- **테스트**: 하위 디렉토리가 포함된 CLI 실행 결과를 정상적으로 보존하는지 검증.

### 위험 평가
- **위험 수준**: 낮음
- **롤백 복잡도**: 쉬움 - `runner/service.py` 복구로 가능
- **테스트 복잡도**: 단순 - 단위/통합 테스트 케이스 추가 및 전체 회귀 테스트 실행

## 워크플로 시각화

```mermaid
flowchart TD
    Start(["R-14 격리 실행 디렉토리 오류"])
    WD["Workspace Detection<br/><b>COMPLETED</b>"]
    RE["Reverse Engineering<br/><b>SKIP</b>"]
    RA["Requirements Analysis<br/><b>COMPLETED</b>"]
    US["User Stories<br/><b>SKIP</b>"]
    WP["Workflow Planning<br/><b>IN PROGRESS</b>"]
    AD["Application Design<br/><b>SKIP</b>"]
    UG["Units Generation<br/><b>SKIP</b>"]
    FD["Functional Design<br/><b>SKIP</b>"]
    NFRA["NFR Requirements<br/><b>SKIP</b>"]
    NFRD["NFR Design<br/><b>SKIP</b>"]
    ID["Infrastructure Design<br/><b>SKIP</b>"]
    CG["Code Generation<br/><b>EXECUTE</b>"]
    BT["Build and Test<br/><b>EXECUTE</b>"]
    OPS["Operations<br/><b>PLACEHOLDER</b>"]
    End(["R-14 완료"])

    Start --> WD --> RE --> RA --> US --> WP --> AD --> UG --> FD --> NFRA --> NFRD --> ID --> CG --> BT --> OPS --> End

    style WD fill:#4CAF50,stroke:#1B5E20,stroke-width:3px,color:#fff
    style RA fill:#4CAF50,stroke:#1B5E20,stroke-width:3px,color:#fff
    style WP fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style CG fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style BT fill:#FFA726,stroke:#E65100,stroke-width:3px,stroke-dasharray:5 5,color:#000
    style RE fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style US fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style AD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style UG fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style FD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style NFRA fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style NFRD fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style ID fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style OPS fill:#BDBDBD,stroke:#424242,stroke-width:2px,stroke-dasharray:5 5,color:#000
    style Start fill:#CE93D8,stroke:#6A1B9A,stroke-width:3px,color:#000
    style End fill:#CE93D8,stroke:#6A1B9A,stroke-width:3px,color:#000
    linkStyle default stroke:#333,stroke-width:2px
```

### 텍스트 대체 표현
1. Workspace Detection 완료
2. Reverse Engineering 생략
3. Requirements Analysis 승인 완료
4. User Stories, Application Design, Units Generation 및 Construction 설계 단계 생략
5. Code Generation에서 `/tmp` 하위 디렉토리 생성 및 결과물 재귀 복사 구현
6. Build and Test에서 단위·통합 및 전체 회귀 테스트 실행
7. Operations는 Placeholder로 종료

## 단계 계획

### INCEPTION PHASE
- [x] Workspace Detection - 완료
- [x] Reverse Engineering - 생략
- [x] Requirements Analysis - 승인 완료
- [x] User Stories - 생략
- [ ] Workflow Planning - 진행 중
- [ ] Application Design - 생략
- [ ] Units Generation - 생략

### CONSTRUCTION PHASE
- [ ] Functional Design - 생략
- [ ] NFR Requirements - 생략
- [ ] NFR Design - 생략
- [ ] Infrastructure Design - 생략
- [ ] Code Generation - 실행 (ALWAYS)
- [ ] Build and Test - 실행 (ALWAYS)

### OPERATIONS PHASE
- [ ] Operations - Placeholder

## 요구사항 검증 계획

| 요구사항 | 인수 기준 | 필수 테스트 증거 | 테스트 수준 | 예정 파일 또는 시나리오 | 필요 결과 |
| --- | --- | --- | --- | --- | --- |
| R-14 | 실제 장애 케이스 호환 | `run_tool` 호출 시 `["-o", "dice_design/octahedron_dice.stl", "dice_design/octahedron_dice.scad"]` 형태의 하위 입출력 경로 성공 검증 | unit/integration | `tests/test_unit_3.py` | Pass |
| R-14 | Path Traversal 방어 | `../escape.stl` 등 상위 탈출 경로나 절대 경로 출력이 차단되는지 검증 | unit/integration | `tests/test_unit_3.py` | Pass (예외 발생) |
| 회귀 방지 | 기존 동작 유지 | 전체 테스트 실행 | regression | `pytest -q` | 모든 테스트 통과 (56개 이상) |

## 성공 기준
- OpenSCAD 실행 전에 workspace 내에 존재하는 모든 하위 디렉토리 구조가 임시 폴더(/tmp) 하위에 동일하게 재생성된다.
- workspace 하위의 모든 `.scad` 소스 파일들이 상대 경로를 유지하여 임시 폴더로 안전하게 복사된다.
- CLI 인자(`args`) 중 `-o` 출력 경로를 정확히 파싱하여, 그에 해당하는 부모 디렉토리가 임시 폴더 내에 미리 생성된다.
- 모든 파일 및 디렉토리 관련 경로는 resolve 후 workspace 내부로 엄격히 제한 및 검증된다.
- 임시 폴더 내의 파일 단위로 크기/수정 시간 스냅샷(Snapshot)을 생성하여 관리하며, 실행 후 스냅샷과 대조해 새로 생성되었거나 변경된 파일만 선별 복사한다.
- `-o`로 명시된 출력 파일은 덮어쓰기를 허용하지만, 그 외 기존 workspace에 있던 파일(입력 소스 등)들을 덮어쓰거나 변경하는 충돌을 철저히 방지한다.
- 기존의 timeout, resource limit, Path Traversal 방어 로직을 완벽히 유지한다.
- 기존 회귀 테스트 및 신규 방어 테스트를 포함한 전체 테스트가 통과한다.
