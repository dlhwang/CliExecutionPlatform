# 비기능 요구사항 정의 계획서 (Unit 3: CLI Runner Service - NFR Requirements Plan)

본 문서는 **Unit 3: CLI Execution Runner**의 비기능 요구사항 정의(NFR Requirements) 및 기술 스택 선정을 위한 계획서 및 의사결정 질문지입니다. 본 계획안은 요구사항의 기준점(Single Source of Truth)으로 작동합니다.

---

## 1. 구현 컨텍스트 및 목적 (Context & Goal)

* **대상 개발 유닛**: Unit 3: CLI Execution Runner
* **목적**: OpenSCAD CLI 실행에 요구되는 레이턴시, 프로세스 동시성, 시스템 가용성 및 리소스 제약(CPU/메모리) 비기능 요구사항을 도출하고 의사결정을 완료합니다.

---

## 2. 의사결정을 위한 공개 질문지 (Open Questions)

> [!IMPORTANT]
> **Unit 3의 비기능 요구사항 수립을 위해 아래 질문에 답변해 주십시오.**  
> 각 질문에 대해 적절한 옵션을 선택하거나 세부 사항을 기재해 주십시오.

### 질문 1. 리소스 제약 (CPU/메모리) 통제 요구사항
OpenSCAD CLI 프로세스 실행 시 무한 루프나 과도한 자원 소비(CPU 100% 점유 또는 메모리 누수)를 예방하기 위한 단기적 리소스 통제 수준은 무엇입니까?

A) 단순 타임아웃(30초) 차단: 호스트 수준에서 subprocess의 30초 라이프사이클 타임아웃만 강제하고, 추가적인 CPU/메모리 물리 한도는 적용하지 않음 (단순 구성)

B) OS 수준 자원 제한 프로파일링: Windows / Linux 등 호스트 운영체제의 기본 프로세스 자원 조회 기능(예: psutil 라이브러리를 활용해 주기적으로 메모리 임계치를 측정하고 오버플로우 시 강제 kill)을 보조적으로 가동하여 자원 폭주 방어

C) Other (please describe after [Answer]: tag below)

[Answer]: A


### 질문 2. 프로세스 동시성 및 세마포어(Semaphore) 제한 정책
여러 사용자의 요청이 동시에 인입되어 여러 OpenSCAD CLI 프로세스가 가동될 때, 호스트 서버의 리소스 고갈을 막기 위한 동시 실행 수 제한(Concurrency Limit)은 몇 개로 설정할까요?

A) 동시 실행 수 최대 2개 제한 (보수적 호스트 보호)

B) 동시 실행 수 최대 5개 제한 (보편적 가용성 제공)

C) 동시 실행 수 제한 없음 (서버 성능 및 OS 스케줄러에 전적으로 위임)

D) Other (please describe after [Answer]: tag below)

[Answer]:A 


### 질문 3. CLI 기동 실패 시 복구성 재시도 정책
CLI 가동을 처음 시도했을 때, 시스템의 일시적인 파일시스템 락이나 일시적인 지연 등으로 인해 프로세스 기동(`Launch`) 자체가 거부되었을 경우 재시도를 수행할까요?

A) 재시도 없음 (Fail-Fast로 Launch 에러를 즉각 보고)

B) 최대 2회 즉시 재시도 시도 후 최종 실패 판정 (일시적인 OS 락 완화 지원)

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## 3. 비기능 요구사항 정의 세부 수행 계획 (NFR Requirements Checklist)

본 계획서 승인 이후 순차적으로 수행할 상세 Checklist입니다.

- [x] **Step 1**: Unit 3 비기능 요구사항 정의서 생성 (`nfr-requirements.md`)
  - [x] 성능(레이턴시), 자원 보호, 가용성, 신뢰성 상세 메트릭 수립 (완료)
- [x] **Step 2**: 기술 스택 결정서 생성 (`tech-stack-decisions.md`)
  - [x] subprocess 실행 라이브러리 및 동시성 제어 도구, psutil 도입 타당성 정리 (완료)
- [x] **Step 3**: 최종 비기능 요구사항 결과물 승인 획득 및 NFR Design 단계로 전이 (완료: 2026-06-19T10:55:00+09:00)
