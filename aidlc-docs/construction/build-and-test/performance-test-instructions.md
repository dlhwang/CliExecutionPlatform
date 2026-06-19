# 성능 테스트 지침서 (Performance Test Instructions)

## 현재 상태

> **MVP 단계에서의 성능 테스트 범위 한정**  
> 본 프로젝트는 MVP(Minimum Viable Product) 단계이며, 성능 요구사항은 다음과 같이 정의되어 있습니다:
> - 최대 동시 CLI 프로세스 실행: **2개** (asyncio.Semaphore)
> - 프로세스 최대 타임아웃: **30초**
> - API Rate Limit: **분당 10회** (slowapi)
> - 최대 동시 오케스트레이션 실행: **2개** (orchestrator/concurrency.py의 Semaphore(2)) 및 10분 wait timeout
> - LLM Client Request 타임아웃: **120초** (httpx.AsyncClient)
>
> 정식 부하 테스트(JMeter, k6 등)는 MVP 이후 스테이징 환경 구축 시 수행 예정입니다.

---

## 현재 검증된 성능 관련 동작

### 1. 동시성 제한 검증 (테스트 기반 검증 완료)

```bash
# Semaphore(2) 동시성 제한 테스트 실행
pytest tests/test_unit_3.py::test_semaphore_limits_concurrency -v
```

- **검증 내용**: 5개 동시 요청 시 최대 2개만 동시 실행됨을 asyncio.gather로 검증
- **결과**: ✅ PASS

### 2. 타임아웃 메커니즘 검증 (테스트 기반 검증 완료)

```bash
pytest tests/test_unit_3.py::test_timeout_kills_process -v
```

- **검증 내용**: 30초 타임아웃 발동 시 즉시 SIGKILL + CLIExecutionTimeoutError 발생
- **결과**: ✅ PASS

### 3. Rate Limiting 검증 (테스트 기반 검증 완료)

```bash
pytest tests/test_unit_1.py::test_rate_limiting -v
```

- **검증 내용**: 분당 10회 초과 시 HTTP 429 응답
- **결과**: ✅ PASS

### 4. 오케스트레이터 동시성 제한 검증 (테스트 기반 검증 완료)

```bash
pytest tests/test_unit_5.py::test_concurrency_gate_limits_two_jobs_and_times_out_waiter -v
```

- **검증 내용**: 3개 이상의 오케스트레이터가 동시 구동 시 2개만 수행되고 3번째는 대기하다 타임아웃 오류가 발생함을 검증
- **결과**: ✅ PASS

### 5. LLM 클라이언트 타임아웃 검증 (테스트 기반 검증 완료)

```bash
pytest tests/test_unit_5.py::test_llm_client_uses_120_second_timeout -v
```

- **검증 내용**: LLM 호출 시 HTTPX 클라이언트의 연결 및 응답 타임아웃이 120초로 올바르게 설정되어 작동함을 검증
- **결과**: ✅ PASS

---

## MVP 이후 부하 테스트 계획 (참고)

### 권장 도구

| 도구 | 목적 |
|------|------|
| `k6` | HTTP API 부하 테스트 (Job 생성 API) |
| `locust` | Python 기반 시나리오 테스트 |
| `hey` | 간단한 API 처리량 측정 |

### 목표 성능 지표 (MVP 이후)

| 지표 | 목표 |
|------|------|
| Job 생성 API 응답 시간 | 95th percentile < 200ms |
| CLI 실행 동시 처리 | 최대 2개 (Semaphore 보장) |
| 타임아웃 정책 | 30초 이내 강제 종료 보장 |
| Rate Limit | 분당 10회/IP 제한 |

### 향후 부하 테스트 실행 예시

```bash
# k6 기반 Job 생성 API 부하 테스트 (스테이징 환경)
k6 run --vus 10 --duration 30s - <<'EOF'
import http from 'k6/http';
export default function () {
  http.post('http://localhost:8000/api/v1/jobs', JSON.stringify({
    prompt: '부하 테스트용 프롬프트'
  }), { headers: { 'Content-Type': 'application/json' } });
}
EOF
```

---

## N/A 사유

공식 부하 테스트 도구 기반 성능 검증은 MVP 단계에서 N/A 처리합니다.  
이유: 로컬 단일 서버 MVP 환경이므로 스테이징 인프라 구축 후 수행이 적절하며,  
핵심 성능 제약(Semaphore, Timeout, Rate Limit)은 단위 테스트로 동작 검증을 완료했습니다.
