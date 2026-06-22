# Hotfix R-12 환경 파일 ASCII 호환성 Code Generation 계획

이 문서는 R-12 Code Generation의 단일 실행 기준이다. 승인 후 아래 단계를 순서대로 수행하고, 각 단계 완료 즉시 같은 상호작용에서 체크박스를 갱신한다.

## 작업 컨텍스트

- **프로젝트 유형**: Brownfield Hotfix
- **Workspace Root**: `D:\workspace\CLI-Execution-Platform`
- **적용 요구사항**: R-12 환경 파일 ASCII 호환성 정책
- **사용자 스토리**: N/A - 사용자 흐름과 API 동작이 없는 설정 템플릿 정책 변경
- **런타임 코드 변경**: 없음
- **데이터베이스 변경**: 없음
- **외부 의존성 변경**: 없음

## 대상 파일

- 수정: `D:\workspace\CLI-Execution-Platform\.env.sample`
- 수정: `D:\workspace\CLI-Execution-Platform\README.md`
- 생성: `D:\workspace\CLI-Execution-Platform\tests\test_env_sample.py`
- 요약 생성: `aidlc-docs/construction/hotfix-r12-env-ascii/code/code-generation-summary.md`

## 제외 파일

- `D:\workspace\CLI-Execution-Platform\.env`
- `D:\workspace\CLI-Execution-Platform\database.py`
- `D:\workspace\CLI-Execution-Platform\limiter.py`
- `D:\workspace\CLI-Execution-Platform\requirements.txt`

## 실행 단계

### Step 1. 변경 전 기준 확인
- [ ] `.env.sample`의 비ASCII 문자가 주석에만 존재하는지 재확인한다.
- [ ] 대상 런타임 소스 파일의 변경 전 Git diff 상태를 기록하여 R-12가 해당 파일을 수정하지 않았음을 검증할 기준을 확보한다.

### Step 2. 환경 파일 템플릿 ASCII 변환
- [ ] `.env.sample`의 한글 주석을 의미가 동일한 영문 ASCII 주석으로 변경한다.
- [ ] 환경 변수 이름과 기존 예시 값은 유지한다.
- [ ] 파일 전체 바이트가 ASCII로 디코딩되는지 확인한다.
- [ ] UTF-8 BOM이 없는지 확인한다.

### Step 3. README 정책 문서화
- [ ] 환경 변수 설정 절에 Windows/SlowAPI 호환성 주의사항을 한국어로 추가한다.
- [ ] 실제 `.env`의 주석과 값에 ASCII 문자만 사용해야 함을 명시한다.
- [ ] 비ASCII 문자가 있으면 시스템 기본 인코딩(CP949) 재해석 과정에서 시작 오류가 날 수 있음을 설명한다.

### Step 4. R-12 정적 검증 테스트 생성
- [ ] `tests/test_env_sample.py`를 생성한다.
- [ ] 저장소 루트를 기준으로 `.env.sample`을 원시 바이트로 읽는다.
- [ ] 원시 바이트가 ASCII로 디코딩되는지 검증한다.
- [ ] 실패 시 비ASCII 문자 재도입 원인을 알 수 있는 명확한 assertion 메시지를 제공한다.

### Step 5. 요구사항 검증
- [ ] 신규 환경 템플릿 테스트를 단독 실행한다.
- [ ] `.env.sample`에서 비ASCII 문자가 검색되지 않는지 정적 확인한다.
- [ ] README에 ASCII-only 및 Windows/SlowAPI 제약이 포함되었는지 확인한다.
- [ ] `database.py`, `limiter.py`, `requirements.txt`에 R-12 구현 변경이 없는지 Git diff로 확인한다.

### Step 6. Code Generation 요약
- [ ] 수정·생성 파일과 검증 결과를 `aidlc-docs/construction/hotfix-r12-env-ascii/code/code-generation-summary.md`에 한국어로 기록한다.
- [ ] R-12 인수 기준별 테스트 증거를 요약한다.
- [ ] 자동화하지 않은 항목이 있으면 N/A 사유와 수동 검증 방법을 기록한다.

## 요구사항 추적성

| 요구사항 | 구현 항목 | 검증 증거 |
| --- | --- | --- |
| R-12: `.env.sample` ASCII-only | Step 2 | ASCII 디코딩 정적 검사 및 신규 테스트 |
| R-12: 영문 템플릿 주석 | Step 2 | 비ASCII 검색 결과 0건 |
| R-12: README 정책 안내 | Step 3 | 문서 내용 검토 |
| R-12: 비ASCII 재도입 방지 | Step 4 | `tests/test_env_sample.py` 통과 |
| R-12: 런타임 코드 미변경 | Step 5 | 대상 런타임 파일 Git diff 확인 |

## 완료 조건

- 모든 실행 단계 체크박스가 `[x]` 상태다.
- `.env.sample`이 ASCII-only이며 UTF-8 BOM이 없다.
- README에 실제 `.env`의 ASCII-only 정책이 명시되어 있다.
- 신규 정적 검증 테스트가 통과한다.
- 런타임 코드와 의존성 파일이 R-12로 인해 변경되지 않았다.
- Code Generation 요약 문서가 생성되었다.
