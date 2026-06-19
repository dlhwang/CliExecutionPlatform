# 비즈니스 로직 모델 - Unit 4: SSE Streaming & Event Catch-up

## 목적

Unit 4는 특정 Job의 진행 이벤트를 `event_logs` 테이블에서 순차적으로 읽어 SSE 클라이언트에 전송합니다. 클라이언트가 연결을 잃은 뒤 `Last-Event-ID`를 포함해 재연결하면, 서버는 해당 ID 이후 이벤트만 먼저 전송하고 이후 실시간 polling 스트림을 이어갑니다.

## 핵심 흐름

1. 클라이언트가 `GET /api/v1/jobs/{job_id}/stream`으로 연결합니다.
2. 서버는 Job 존재 여부와 API Key 또는 지정 헤더 기반 접근 권한을 검증합니다.
3. 서버는 `Last-Event-ID` 헤더를 읽습니다.
4. `Last-Event-ID`가 없으면 `last_seen_id = 0`으로 시작합니다.
5. `Last-Event-ID`가 숫자가 아니거나 해당 Job의 이벤트 범위에 없으면 값을 무시하고 첫 이벤트부터 전송합니다.
6. 서버는 `event_logs`에서 `job_id`가 일치하고 `id > last_seen_id`인 이벤트를 `id` 오름차순으로 조회합니다.
7. 조회된 이벤트를 SSE 프레임으로 전송하고, 마지막으로 전송한 `EventLog.id`를 `last_seen_id`로 갱신합니다.
8. 누락 이벤트 전송 후에도 Job이 `RUNNING` 또는 `CREATED` 상태이면 0.5초 간격으로 polling을 계속합니다.
9. Job이 `COMPLETED` 또는 `FAILED` 상태이고 더 이상 전송할 이벤트가 없으면 종료 이벤트를 전송한 뒤 스트림을 닫습니다.

## 연결 종료 Job 처리

이미 종료된 Job에 대해 SSE 연결이 들어오면 서버는 연결을 거절하지 않습니다. 저장된 이벤트를 모두 catch-up 전송한 뒤 종료 이벤트를 보내고 스트림을 닫습니다. 이를 통해 새로고침 또는 늦은 접속 상황에서도 사용자는 최종 로그를 확인할 수 있습니다.

## 이벤트 조회 알고리즘

```text
Input: job_id, last_event_id_header

1. validate_access(job_id, request_headers)
2. job = find_job(job_id)
3. if job does not exist: return 404
4. last_seen_id = parse_last_event_id_or_zero(last_event_id_header)
5. if last_seen_id is invalid for this job: last_seen_id = 0
6. loop:
   a. logs = find EventLog where job_id = job_id and id > last_seen_id order by id asc
   b. for each log:
      - emit SSE frame with id = log.id, event = log.event_type, data = serialized log payload
      - last_seen_id = log.id
   c. refresh job status
   d. if job status is COMPLETED or FAILED and no pending logs remain:
      - emit terminal SSE frame
      - close stream
   e. wait 0.5 seconds
```

## SSE 프레임 규격

SSE `event` 필드는 기존 `EventLog.event_type` 값을 그대로 사용합니다.

```text
id: {event_log.id}
event: {event_log.event_type}
data: {"job_id":"...","event_id":123,"event_type":"CLI_OUTPUT","message":"...","created_at":"..."}
```

종료 프레임은 DB 이벤트가 아니라 스트림 제어용 프레임입니다.

```text
event: STREAM_END
data: {"job_id":"...","status":"COMPLETED"}
```

## 다중 연결 모델

MVP에서는 같은 Job에 대한 여러 SSE 연결을 허용합니다. 각 연결은 독립적으로 catch-up과 DB polling을 수행합니다. 추후 연결 수가 증가하면 Job별 fan-out, queue, pub/sub 구조로 최적화할 수 있으나 Unit 4 MVP 범위에서는 단순 polling을 우선합니다.

## 오류 흐름

- Job이 없으면 HTTP 404로 연결을 거절합니다.
- API Key 또는 필수 헤더가 없거나 잘못되면 HTTP 403으로 연결을 거절합니다.
- 잘못된 `Last-Event-ID`는 오류로 보지 않고 첫 이벤트부터 재전송합니다.
- polling 중 DB 오류가 발생하면 오류 이벤트를 전송 가능한 경우 전송한 뒤 스트림을 종료합니다.
