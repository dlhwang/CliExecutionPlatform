# 빌드 지침서 (Build Instructions)
# CLI Execution Platform - Backend

## 사전 요구 사항 (Prerequisites)

| 항목 | 버전 / 설명 |
|------|-----------|
| **런타임** | Python 3.10 이상 |
| **패키지 관리자** | pip (venv 가상 환경 권장) |
| **데이터베이스** | PostgreSQL 14+ (프로덕션) / SQLite (테스트 전용) |
| **운영 체제** | Linux, macOS, Windows 지원 |
| **디스크 공간** | 최소 500MB (venv 포함) |

### 환경 변수 (Environment Variables)

| 변수명 | 설명 | 필수 여부 |
|-------|------|---------|
| `DATABASE_URL` | PostgreSQL 접속 URL (`postgresql://user:pass@host:5432/db`) | 필수 |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 (콤마 구분, 개발 시 `*` 가능) | 선택 |
| `OPENSCAD_BIN_PATH` | OpenSCAD CLI 실행 파일 절대 경로 | 선택 (기본값: `openscad`) |

---

## 빌드 단계 (Build Steps)

### 1. 저장소 클론 및 디렉토리 이동

```bash
git clone <repository-url>
cd CLI-Execution-Platform
```

### 2. 가상 환경 생성 및 활성화

```bash
# 가상 환경 생성
python -m venv venv

# 활성화 (Linux/macOS)
source venv/bin/activate

# 활성화 (Windows PowerShell)
venv\Scripts\Activate.ps1
```

### 3. 의존 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

```bash
# .env.sample을 복사하여 실제 값 입력
cp .env.sample .env
# .env 파일에서 DATABASE_URL 등 설정
```

### 5. 애플리케이션 기동 (개발 서버)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 빌드 성공 검증

- **기대 출력**: `INFO: Uvicorn running on http://0.0.0.0:8000`
- **헬스체크**: `GET http://localhost:8000/docs` → FastAPI Swagger UI 확인
- **빌드 산출물**: 실행 가능한 ASGI 애플리케이션 (`main.py:app`)

---

## 디렉토리 구조 (Project Structure)

```
CLI-Execution-Platform/
├── main.py               # FastAPI 진입점
├── database.py           # SQLAlchemy 엔진 + 세션 팩토리
├── limiter.py            # slowapi Rate Limiter
├── requirements.txt      # 의존 패키지 목록
├── jobs/                 # Job 도메인
├── storage/              # 파일 저장소 추상화
├── llm/                  # LLM 파서 및 보안 검증기
├── runner/               # CLI 실행 서비스
├── sse/                  # SSE 스트리밍 서비스
├── orchestrator/         # 반복 수정 오케스트레이터 서비스
└── tests/                # 통합 테스트
```

---

## 트러블슈팅 (Troubleshooting)

### 의존성 설치 오류

- **원인**: pip 버전이 오래되었거나 가상 환경이 활성화되지 않음
- **해결**: `pip install --upgrade pip` 후 재시도

### `DATABASE_URL` 연결 오류

- **원인**: PostgreSQL 서버 미기동 또는 접속 정보 오류
- **해결**: `.env`의 `DATABASE_URL` 값 확인 후 PostgreSQL 서버 상태 점검

### `OPENSCAD_BIN_PATH` 관련 오류

- **원인**: OpenSCAD가 미설치되었거나 PATH에 없음
- **해결**: OpenSCAD 설치 후 `.env`에 절대 경로 설정 (테스트 실행 시에는 불필요)
