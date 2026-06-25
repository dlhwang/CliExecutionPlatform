# Requirements Clarification Questions - FEATURE R-18 (AI-MAKING multi-turn SCAD)

AI-MAKING 워크플로우(`D:\workspace\scad\ai-making-rules\core-workflow.md`)를 기반으로 한 멀티턴 CAD/SCAD 생성 플랫폼 개발 방향을 구체화하기 위한 질문입니다.

## Question 1
AI-MAKING 워크플로우의 단계들(요구사항 분석, 재료/가공 분석, 측정 계획, 테스트 쿠폰 설계, 최종 모델링, 조립 가이드 등)을 시스템 내부적으로 어떻게 표현하고 실행해야 합니까?

A) 시스템 백엔드에 새로운 오케스트레이터(예: `AIMakingOrchestratorService`) 혹은 상태 머신을 구축하여 각 단계를 순차적인 하위 작업(Sub-job) 또는 트랜잭션으로 자동 실행하고 기록합니다.

B) 프론트엔드 UI/대화 화면에서 각 단계별 상태(예: Inception 단계 질문 답변, 측정값 입력 등)를 사용자에게 명시적으로 노출하고, 사용자의 명시적 승인(Approve)을 받으며 한 단계씩 전진하는 세부적 멀티턴 구조를 가집니다.

C) 기존 오케스트레이터 구조를 재활용하되, LLM의 System Prompt와 Context 구조 내에서 에이전트 스스로 해당 단계를 시뮬레이션하고 최종 SCAD 및 관련 산출물을 루프 형태로 점진적 수정(Refinement)하여 한 번에 출력하도록 합니다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B가 좋을 것 같은데, 이러면 LLM으로 보내는 토큰양이 걱정되긴하거덩 멀티턴이래 봤다 어차피 다 던지는 거 아니냐 뭐 좋은 생각 없니

## Question 2
물리적 CAD 설계에서 매우 중요한 실측 측정치(Measured Specs) 및 공차(Fit Tolerance) 관리를 플랫폼 레벨에서 어떻게 지원해야 합니까?

A) 사용자가 UI 폼이나 특정 API를 통해 주요 피팅 대상(예: 베어링 지름, 볼트 규격 등)의 실측치와 허용 공차를 직접 테이블 형태로 입력할 수 있는 구조를 제공하고, 이 데이터를 JSON 파라미터로 LLM에게 강제 주입합니다.

B) LLM이 먼저 측정 계획(`measurement-plan.json`) 파라미터 규격을 제안하여 파일로 작성하게 하고, 사용자가 해당 파일을 직접 수정하거나 컨텍스트로 답변을 덧붙여 실제 치수를 확정하도록 유도합니다.

C) 복잡한 구조 없이, 단순히 사용자가 자연어 대화 창에 "샤오미 워치 가로 42mm, 세로 45mm, 두께 12mm"와 같이 입력하면 LLM이 프롬프트 컨텍스트로 인식하도록 자유도를 둡니다.

D) Other (please describe after [Answer]: tag below)

[Answer]: C 이고 싶은데 사용자가 처음부터 수치를 자세하게 줄리 없으니까 되물어 보는 방향으로 하고 싶어

## Question 3
재료 결합부나 홀 공차 등을 미리 제작하여 검증하는 '테스트 쿠폰(Test Coupon)' 단계를 플랫폼 실행 및 검증 흐름에서 어떻게 다룰까요?

A) 본 모델(SCAD)을 만들기 전에, 공차 및 접합부 치수 검증만을 위한 단순화된 테스트 조각인 `test_coupon.scad` 파일을 LLM이 먼저 설계·렌더링하게 하고, 이에 대한 가공/조립성 피드백을 사용자에게 우선 수집합니다.

B) 별도의 테스트 쿠폰 설계 단계를 두지 않고, 본 모델 생성 시 오픈스캐드(OpenSCAD) CLI 렌더링 검증 및 `ScadStaticValidator`의 정적 체크를 통해서만 설계 오류를 걸러냅니다.

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 (Security Extensions)
이 프로젝트에 보안 확장(Security Extension) 규칙들을 차단 제약 조건으로 강제 적용하시겠습니까?

A) Yes — 모든 보안(SECURITY) 규칙을 차단 제약으로 강제 적용합니다. (프로덕션 등급 애플리케이션 개발에 권장)

B) No — 모든 보안 규칙 적용을 건너뜁니다. (PoC, 프로토타입 및 실험용 프로젝트에 적합)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5 (Property-Based Testing Extension)
이 프로젝트에 속성 기반 테스트(Property-Based Testing, PBT) 확장 규칙들을 강제 적용하시겠습니까?

A) Yes — 모든 PBT 규칙을 차단 제약으로 강제 적용합니다. (비즈니스 로직, 데이터 변환, 직렬화 또는 상태 저장 컴포넌트가 있는 프로젝트에 권장)

B) Partial — 순수 함수 및 직렬화 라운드 트립에 대해서만 PBT 규칙을 강제 적용합니다. (알고리즘 복잡도가 제한적인 프로젝트에 적합)

C) No — 모든 PBT 규칙 적용을 건너뜁니다. (단순 CRUD 애플리케이션, UI 전용 프로젝트 또는 비즈니스 로직이 없는 얇은 통합 레이어에 적합)

X) Other (please describe after [Answer]: tag below)

[Answer]: C
