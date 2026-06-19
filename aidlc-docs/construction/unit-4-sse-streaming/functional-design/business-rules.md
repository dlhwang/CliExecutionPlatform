# 비즈니스 규칙 - Unit 4: SSE Streaming & Event Catch-up

## BR-4-1: Job 존재 검증

SSE 스트림은 존재하는 Job에 대해서만 열 수 있습니다. `job_id`에 해당하는 Job이 없으면 HTTP 404를 반환합니다.

## BR-4-2: MVP 접근 검증

Unit 4 MVP는 사용자 인증/소유자 검증 대신 API Key 또는 지정 헤더 기반 검증을 포함합니다.

- 서버는 환경 변수 또는 설정값으로 허용된 스트림 접근 키를 가진다고 가정합니다.
- 클라이언트는 요청 헤더에 해당 키를 전달해야 합니다.
- 헤더가 없거나 값이 일치하지 않으면 HTTP 403을 반환합니다.
- 사용자 계정 기반 소유자 검증은 MVP 이후 범위로 둡니다.

## BR-4-3: Last-Event-ID 처리

`Last-Event-ID`는 catch-up 시작점을 나타내는 이벤트 ID입니다.

- 값이 없으면 첫 이벤트부터 전송합니다.
- 값이 숫자가 아니면 무시하고 첫 이벤트부터 전송합니다.
- 값이 해당 Job의 이벤트 범위에 없으면 무시하고 첫 이벤트부터 전송합니다.
- 값이 유효하면 `id > Last-Event-ID` 조건으로 누락 이벤트만 전송합니다.

## BR-4-4: 이벤트 순서 보장

모든 이벤트는 `EventLog.id` 오름차순으로 전송해야 합니다. 동일 Job에 대해 `idx_event_logs_job_id_id` 인덱스를 사용해 `job_id`, `id` 기반 조회를 수행합니다.

## BR-4-5: SSE 이벤트명

SSE `event` 필드는 기존 `EventLog.event_type` 값을 그대로 사용합니다.

예시:

- `SYSTEM`
- `SYSTEM_EVENT`
- `CLI_OUTPUT`
- `SECURITY_ALERT`

클라이언트 친화적인 이벤트명 매핑은 하지 않습니다. 클라이언트는 서버가 저장한 이벤트 타입을 그대로 해석합니다.

## BR-4-6: polling 간격

실시간 스트림은 0.5초 간격으로 DB를 polling합니다. 이 값은 MVP 기준 고정값으로 설계하며, 추후 설정값으로 분리할 수 있습니다.

## BR-4-7: 종료된 Job 연결 처리

Job이 이미 `COMPLETED` 또는 `FAILED` 상태여도 SSE 연결을 허용합니다. 서버는 저장된 이벤트를 모두 전송한 뒤 `STREAM_END` 이벤트를 보내고 스트림을 닫습니다.

## BR-4-8: 실행 중 Job 종료 처리

스트리밍 중 Job 상태가 `COMPLETED` 또는 `FAILED`로 바뀌면 서버는 아직 전송되지 않은 이벤트를 모두 전송한 뒤 `STREAM_END` 이벤트를 보내고 스트림을 닫습니다.

## BR-4-9: 다중 연결 허용

같은 Job에 대해 여러 SSE 클라이언트 연결을 허용합니다. MVP에서는 각 연결이 독립적으로 DB polling을 수행합니다. 이 정책은 단순성과 구현 속도를 우선하며, 연결 fan-out 최적화는 후속 개선으로 둡니다.

## BR-4-10: 오류 전송 규칙

SSE 연결 수립 전 검증 오류는 HTTP 오류 응답으로 반환합니다. 연결 수립 후 내부 오류가 발생하면 가능할 경우 `SYSTEM_EVENT` 또는 `STREAM_ERROR` 이벤트를 전송한 뒤 스트림을 종료합니다.

## BR-4-11: 메시지 본문 직렬화

`data` 필드는 JSON 문자열로 직렬화합니다. 최소 포함 필드는 다음과 같습니다.

- `job_id`
- `event_id`
- `event_type`
- `message`
- `created_at`

## BR-4-12: 데이터 변경 금지

SSE 스트림은 읽기 전용 기능입니다. 스트림 요청은 Job 상태, EventLog 내용, Artifact, Workspace를 변경하면 안 됩니다.
