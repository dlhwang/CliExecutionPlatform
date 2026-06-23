# 빌드 지침 (Build Instructions)

본 지침은 CLI-Execution-Platform 프로젝트의 전체 빌드 및 환경 구성 단계를 설명합니다.

## 필수 요구사항 (Prerequisites)
- **런타임 및 빌드 도구**: Python 3.13+ 및 pip
- **가상환경 도구**: venv (Python 내장 패키지)
- **종속성 라이브러리**: `requirements.txt`에 명시된 외부 라이브러리 (FastAPI, SQLAlchemy, Uvicorn, SlowAPI, PyJWT 등)
- **데이터베이스**: SQLite (로컬 테스트용) 또는 PostgreSQL (실행/배포 환경)
- **시스템 요구사항**: Windows / Linux / macOS (현재 로컬 검증은 Windows 11 환경 기준)

## 환경 설정 및 빌드 단계

### 1. 가상환경 생성 및 활성화
```bash
# 가상환경 생성
python -m venv venv

# Windows PowerShell에서 가상환경 활성화
.\venv\Scripts\Activate.ps1

# Linux/macOS에서 가상환경 활성화
source venv/bin/activate
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 파일 설정
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 필요한 환경 설정을 추가합니다. `.env.sample` 파일을 참고하여 설정할 수 있습니다.
```bash
cp .env.sample .env
```
*주의*: `.env` 파일은 UTF-8(BOM 없음) 인코딩으로 저장되어야 합니다.

### 4. 데이터베이스 마이그레이션 (필요시)
Alembic 등을 이용한 데이터베이스 초기화 스키마를 확인합니다. 본 프로젝트는 실행 시 SQLAlchemy ORM `Base.metadata.create_all`을 통해 필요한 테이블 구조를 자동 생성합니다.

### 5. 빌드 및 구성 검증
```bash
# PYTHONPATH 설정 및 Uvicorn 개발 서버 정상 구동 확인
$env:PYTHONPATH="."
python main.py
```
- **기대 결과**: Uvicorn 서버가 `http://127.0.0.1:8000`에서 정상적으로 구동되고 API 문서(docs)에 접속 가능해야 합니다.

## 트러블슈팅

### 1. UnicodeDecodeError (cp949 관련)
- **원인**: Windows 환경에서 `.env` 파일을 로드할 때 시스템 기본 인코딩(CP949)으로 파일 읽기를 시도하여 발생합니다.
- **해결책**: `.env` 파일이 UTF-8(BOM 없음)로 저장되었는지 확인하고, `main.py`나 `limiter.py`에서 `dotenv` 패키지의 `load_dotenv` 호출 시 명시적으로 `encoding="utf-8"` 파라미터를 지정하도록 코드가 이미 조치되어 있습니다.

### 2. ModuleNotFoundError: No module named 'database'
- **원인**: 파이썬 인터프리터가 프로젝트 루트 경로를 모듈 탐색 경로에 포함하지 않아 발생합니다.
- **해결책**: 환경 변수로 `PYTHONPATH`를 `.` 또는 프로젝트 루트의 절대 경로로 명시해야 합니다. (예: `$env:PYTHONPATH="."`)
