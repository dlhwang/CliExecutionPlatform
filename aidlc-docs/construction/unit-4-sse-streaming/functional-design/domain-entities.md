# 도메인 엔티티 - Unit 4: SSE Streaming & Event Catch-up

## 기존 엔티티 재사용

Unit 4는 새로운 영속 엔티티를 만들지 않고 Unit 1에서 정의한 `Job`과 `EventLog`를 사용합니다.

## Job

Job은 SSE 스트림의 대상 작업입니다.

| 필드 | 타입 | 역할 |
|---|---|---|
| `id` | UUID | 스트림 대상 Job 식별자 |
| `status` | string | 스트림 지속 또는 종료 판단 기준 |
| `created_at` | datetime | Job 생성 시각 |
| `updated_at` | datetime | 상태 갱신 시각 |

### 상태 의미

| 상태 | SSE 동작 |
|---|---|
| `CREATED` | 연결 허용, 이벤트 polling 지속 |
| `RUNNING` | 연결 허용, 이벤트 polling 지속 |
| `COMPLETED` | 누락 이벤트 전송 후 종료 이벤트를 보내고 닫음 |
| `FAILED` | 누락 이벤트 전송 후 종료 이벤트를 보내고 닫음 |

## EventLog

EventLog는 SSE로 전송되는 원천 이벤트입니다.

| 필드 | 타입 | 역할 |
|---|---|---|
| `id` | integer | SSE `id` 및 catch-up 기준 |
| `job_id` | UUID | 이벤트가 속한 Job |
| `event_type` | string | SSE `event` 필드 값 |
| `message` | text | 클라이언트에 전달할 메시지 |
| `created_at` | datetime | 이벤트 생성 시각 |

### 조회 규칙

Unit 4는 다음 조건으로 이벤트를 조회합니다.

```text
EventLog.job_id == job_id
EventLog.id > last_seen_id
ORDER BY EventLog.id ASC
```

## SSEStreamCursor

영속 엔티티가 아닌 스트림 연결 단위의 런타임 값입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `job_id` | UUID | 현재 스트림 대상 |
| `last_seen_id` | integer | 마지막으로 클라이언트에 전송한 EventLog ID |
| `poll_interval_seconds` | float | polling 간격, MVP 기본값 0.5 |
| `is_terminal` | boolean | Job 종료 상태 도달 여부 |

## SSEEventFrame

클라이언트로 전송되는 논리 이벤트 프레임입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | integer 또는 null | EventLog 기반 이벤트는 `EventLog.id`, 제어 이벤트는 null 가능 |
| `event` | string | `EventLog.event_type` 또는 스트림 제어 이벤트명 |
| `data` | object | JSON 직렬화 대상 데이터 |

## StreamAccessCredential

MVP 접근 검증을 위한 런타임 값입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `header_name` | string | API Key 또는 접근 키를 담는 요청 헤더명 |
| `expected_value` | string | 서버 설정에 저장된 기대값 |
| `provided_value` | string 또는 null | 클라이언트 요청에서 읽은 값 |

## 엔티티 관계

```text
Job 1 ---- N EventLog

SSEStreamCursor references Job.id
SSEEventFrame is built from EventLog
StreamAccessCredential validates stream request before cursor creation
```
