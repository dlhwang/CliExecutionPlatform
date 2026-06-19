# 기술 스택 결정서 (Technology Stack Decisions) - Unit 2: Parser & Policy Validator Service

본 문서는 **Unit 2: Parser & Policy Validator Service**에서 채택한 기술 요소 및 상세 라이브러리 선정 배경, 예외 설계 사안을 요약 기술합니다.

---

## 1. 선정된 기술 스택 명세 (Technology Inventory)

* **JSON 데이터 바인딩 및 스키마 검증**: `Pydantic 2.x` (Pydantic BaseModel, Field, ConfigDict, Annotated, TypeAdapter)
* **마크다운 텍스트 파싱**: Python 기본 표준 패키지 `re` (정규 표현식 엔진)
* **물리적 파일 속성 및 절대경로 검사**: Python 기본 표준 패키지 `pathlib.Path`

---

## 2. 세부 선정 배경 및 아키텍처 의사결정 (Decisions & Rationale)

### 2.1 Pydantic 2.x 채택
* **배경**: LLM이 산출한 액션 JSON 목록을 다형성 리스트(Union 형태)로 직렬화하여 형식을 안전하게 검증해야 합니다.
* **이유**: Pydantic 2.x는 Rust 기반 코어로 컴파일되어 이전 1.x 버전에 비해 최대 10~20배 가량 빠르며, 다형성 리스트를 판별해 내는 식별자 유니온(`discriminator`) 문법이 내장되어 있어 복잡한 조건 분기 없이 간결하게 다형성 DTO 검증을 구현할 수 있습니다.

### 2.2 Python `re` 모듈 및 Fallback 문자열 처리
* **배경**: 마크다운 원문에 섞여 있는 JSON 코드 블록을 추출해야 합니다.
* **이유**: 타사 마크다운 파서 라이브러리(CommonMark, Mistune 등)는 무겁고 설치 의존성을 늘리며, 단순 텍스트 내에서 JSON 블록만 추출하기에는 비효율적입니다. 표준 `re` 모듈의 정규식 컴파일을 사용하여 `(?s)```json\s*(.*?)\s*``` ` 구문을 활용해 1ms 이내로 안전하게 코드 세그먼트를 발라내며, 예외적인 2차 Fallback(인덱스 자르기) 루프를 직접 설계하여 가벼우면서도 견고하게 오작동을 극복합니다.

### 2.3 `pathlib.Path`를 활용한 물리 검증
* **배경**: 절대경로 침투, 심볼릭 링크 등 시스템 중요 영역을 우회하려는 공격을 방어해야 합니다.
* **이유**: `os.path` 계열 함수들에 비해 `pathlib.Path` 객체는 객체 지향적인 경로 연산이 가능하며, 윈도우와 리눅스 등 다종 OS 디스크 특성 차이를 완전 격리하여 검사해 줍니다. 특히 `Path.resolve().is_relative_to(base_dir)` 및 `Path.is_symlink()` 메서드를 통해 단 몇 줄의 직관적인 코드로 복잡한 침투 방어 논리를 완벽하게 실현할 수 있습니다.

### 2.4 커스텀 예외 클래스 설계 (`LLMPlanRetryableException` 등)
* **배경**: LLM API 호출은 고비용 연산이므로 단순 형식 오류 시 즉시 FAILED 종결을 막아야 합니다.
* **이유**:
  - **`LLMPlanRetryableException`**: JSON 구문 에러나 디코딩 실패 시 발생합니다. 상위 오케스트레이터가 이 예외를 가려내어 LLM에 문법 가이드를 보강해 재호출할 수 있도록 구조적 뼈대를 마련합니다.
  - **`LLMPlanValidationError`**: 형식에 맞지 않는 불법 액션 타입이거나, 보안 침투(Traversal 등) 위반 시 던집니다. 이는 재시도 가치가 없는 비정상 공격 시도 혹은 복구 불가능 스키마 에러이므로 즉시 Job을 FAILED 처리하고 침투 탐지 경고를 날리게 차별화합니다.
