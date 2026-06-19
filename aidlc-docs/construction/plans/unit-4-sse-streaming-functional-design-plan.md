# 기능 설계 계획서 - Unit 4: SSE Streaming & Event Catch-up

## 목적

Unit 4는 Job 진행 상태와 CLI 실행 로그를 Server-Sent Events(SSE)로 실시간 전달하고, 연결 단절 후 `Last-Event-ID` 기반으로 누락 이벤트를 복구 전송하는 기능을 담당합니다.

## 설계 범위

- SSE 엔드포인트 `/api/v1/jobs/{job_id}/stream`
- `event_logs` 테이블 기반 이벤트 조회 및 전송
- 0.5초 간격의 비동기 SQL polling 루프
- `Last-Event-ID` 기반 catch-up 전송
- Job 종료 상태(`COMPLETED`, `FAILED`) 도달 시 스트림 종료 규칙
- SSE 이벤트 포맷과 오류 응답 규칙

## 실행 체크리스트

- [x] Step 1: Unit 4 책임과 경계 분석 완료
- [x] Step 2: 관련 요구사항 R-4, Story S-2, Story S-3 추적 완료
- [x] Step 3: 기존 `Job` / `EventLog` 도메인 모델 확인 완료
- [x] Step 4: 기능 설계 질문 작성 완료
- [x] Step 5: 사용자 답변 수집 및 모호성 검토 완료
- [x] Step 6: 기능 설계 산출물 작성 완료
  - [x] `business-logic-model.md`
  - [x] `business-rules.md`
  - [x] `domain-entities.md`
- [x] Step 7: 기능 설계 완료 메시지 제시 및 승인 대기
- [x] Step 8: 승인 기록 및 `aidlc-state.md` 진행 상태 갱신 완료 (2026-06-19T13:28:08+09:00)

## 사용자 답변 반영 결과

| 질문 | 답변 | 설계 반영 |
|---|---|---|
| Q1. 종료된 Job 연결 처리 | A | 저장된 이벤트를 모두 catch-up 전송한 뒤 종료 이벤트를 보내고 스트림을 닫음 |
| Q2. 잘못된 `Last-Event-ID` 처리 | A | 잘못된 값은 무시하고 첫 이벤트부터 전송 |
| Q3. SSE `event` 필드 | A | 기존 `EventLog.event_type` 값을 그대로 사용 |
| Q4. 접근 검증 | B | API Key 또는 헤더 기반 검증 포함 |
| Q5. 다중 연결 | B | 다중 연결 허용, MVP에서는 단순 polling으로 구현하고 최적화는 후속 과제로 기록 |
