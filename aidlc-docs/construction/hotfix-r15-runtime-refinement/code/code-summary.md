# R-15A/B/C 코드 생성 요약

## 변경 결과

- R-15A: 주석과 double-quoted string literal을 원본 위치 보존 방식으로 masking하여 syntax-like 정적 검증의 오탐을 방지했습니다.
- R-15B: stdout/stderr를 동시에 drain하고 각 line을 기존 `CLI_OUTPUT` 이벤트로 저장하면서 스트림별 bounded tail을 `CLIExecutionError`에 보존했습니다.
- R-15B: empty top-level 및 2D/3D 혼용 메시지를 안정적인 Rule ID로 변환하는 bounded diagnostics를 추가했습니다.
- R-15C: `generate_actions`가 parse → validation → execution refinement를 소유하도록 실행 흐름을 단일화했습니다.
- R-15C: attempt 전 workspace/artifact snapshot, 실패 rollback, artifact 승격 지연 정책을 적용했습니다.
- R-15C: 성공적으로 실행되고 저장된 최종 plan만 반환하며, 이후에만 Job을 `COMPLETED`로 전이합니다.

## 변경 파일

- 정적 검증: `llm/scad_validator.py`
- retry 제어: `llm/retry.py`
- runner 예외·출력·진단: `runner/exceptions.py`, `runner/service.py`, `runner/diagnostics.py`
- 실행·상태 흐름: `orchestrator/actions.py`, `orchestrator/service.py`
- attempt snapshot 계약: `storage/interface.py`, `storage/local.py`
- 검증 테스트: `tests/test_unit_2.py`, `tests/test_unit_3.py`, `tests/test_unit_5.py`

## 검증 결과

- `tests/test_unit_2.py`: 19개 통과
- `tests/test_unit_3.py`: 14개 통과
- `tests/test_unit_5.py`: 21개 통과
- 전체 회귀 테스트: 79개 통과
- Python compileall: 통과
- Docker/OpenSCAD 실제 컨테이너 smoke: Code Generation 단계에서는 미실행, Build and Test 단계에서 별도 판단

## 요구사항 추적성

- R-15A comment/string masking 및 bounded feedback: `tests/test_unit_2.py`
- R-15B concurrent drain, EventLog, bounded exception 및 diagnostics: `tests/test_unit_3.py`
- R-15C current-attempt feedback, rollback, artifact 비승격, 최종 plan 저장 및 상태 전이: `tests/test_unit_5.py`
