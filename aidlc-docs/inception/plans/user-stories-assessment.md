# 사용자 스토리 필요성 평가 (User Stories Assessment)

## Request Analysis (요구사항 분석)
- **Original Request (원본 요청)**: 사용자가 자연어로 OpenSCAD 등의 설계 결과물을 요청하면, 서버가 Job을 생성하고 LLM이 작업 계획(JSON Action Plan)을 수립하여 호스트 환경에서 안전하게 실행 및 그 과정을 SSE로 실시간 전송하고 최종 Artifact를 다운로드 가능하게 제공하는 플랫폼.
- **User Impact (사용자 영향도)**: **Direct (직접적)** - 사용자는 웹/CLI 인터페이스를 통해 자연어로 작업을 요청하고, SSE 기반의 실시간 로그 화면을 모니터링하며, 최종 완성된 설계 및 이미지 파일을 다운로드하는 전체적인 UX 시나리오를 직접 겪게 됨.
- **Complexity Level (복잡도 수준)**: **Complex (복잡)** - 단순 API 동작뿐 아니라 실시간 비동기 이벤트 스트리밍, Last-Event-ID 기반 복구, 격리된 CLI 실행, 입력값 검증 등 프론트-백엔드 간의 유기적인 사용자 상호작용 설계가 요구됨.
- **Stakeholders (이해관계자)**: 최종 사용자(End-user), 시스템 관리자/아키텍트(System Administrator/Architect), LLM 에이전트.

## Assessment Criteria Met (평가 기준 충족 여부)
- [x] **High Priority Indicator**: 
  - 신규 사용자 기능 개발 (자연어 기반 작업 요청 및 Artifact 다운로드)
  - 사용자 경험(UX) 변화 (SSE 실시간 진행률 및 로그 모니터링)
  - 복잡한 비즈니스 로직 (LLM Action Plan 검증, Last-Event-ID 기반 누락 복구)
- [x] **Medium Priority Indicator**:
  - 보안 강화 (디렉토리 traversal 방지, Command Injection 방지 등 사용자에 직접적인 영향을 미치는 보안 정책)
- [x] **Benefits**: 
  - 자연어 요청부터 최종 다운로드 및 SSE 복구에 이르는 사용자 관점의 흐름을 기능적으로 명확히 규정하여 누락 없는 개발이 가능해짐.
  - 구체적인 Acceptance Criteria를 바탕으로 수동/자동 테스트 케이스 정의가 수월해짐.

## Decision (결정)
**Execute User Stories (사용자 스토리 진행 여부)**: **Yes (진행)**
**Reasoning (논거)**: 본 플랫폼은 프론트엔드/사용자 애플리케이션과 백엔드 엔진 간의 실시간 비동기 interaction(SSE 로그 스트리밍, Last-Event-ID 복구)이 가장 중요한 핵심 가치 중 하나입니다. 사용자 스토리 작성을 통해 '사용자가 겪는 시나리오'와 '이벤트를 전달받는 과정'을 중심으로 인수 기준(Acceptance Criteria)을 세부화하는 것이 아키텍처 및 상세 구현의 완성도를 높이는 데 크게 기여합니다.

## Expected Outcomes (기대 결과)
- 사용자 중심의 유즈케이스 시나리오 확립 (자연어 요청 -> 대기/SSE 구독 -> 실시간 로깅 -> 다운로드)
- Last-Event-ID 복구 기능에 대한 테스트 가능한 인수 기준(Given/When/Then) 수립
- 개발 단계에서 각 컴포넌트별로 추적 가능한 Verification Expectations 마련

---

## R-16 Artifact ID 기반 보안 다운로드 평가

### Request Analysis
- **Original Request**: 클라이언트가 경로나 파일명을 제공하지 않고 `artifact_id`만으로 안전하게 결과물을 다운로드하는 API를 추가한다.
- **User Impact**: Direct - 외부 클라이언트와 사용자가 다운로드 API 계약 및 오류 응답을 직접 소비한다.
- **Complexity Level**: Medium - 등록·다운로드의 이중 경로 검증, 403/404 경계, 응답 헤더 계약이 포함된다.
- **Stakeholders**: API 클라이언트 개발자, 최종 사용자, 플랫폼 운영자

### Assessment Criteria Met
- [x] **High Priority**: 고객 노출 API와 신규 사용자 기능
- [x] **Medium Priority**: 보안 강화와 데이터 모델 변경
- [x] **Benefits**: 등록 경계와 다운로드 경계를 사용자 관점의 검증 가능한 시나리오로 분리하고 API 오류 계약을 명확히 한다.

### Decision
**Execute User Stories**: Yes

**Reasoning**: 외부 소비자가 직접 사용하는 API이며 정상 다운로드, 잘못된 메타데이터, 누락 파일, 경로 공격이 서로 다른 관찰 가능한 결과를 가진다. 사용자 스토리는 R-16 요구사항과 자동화 테스트 간 추적성을 제공한다.

### Expected Outcomes
- API 소비자와 최종 사용자 관점의 다운로드 성공 기준 정의
- Artifact 등록자와 다운로드 요청자의 보안 경계 분리
- HTTP 403/404 및 응답 헤더 계약의 테스트 추적성 확보
