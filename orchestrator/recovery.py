from datetime import datetime, timedelta, timezone

from orchestrator.repository import OrchestratorRepository

STALE_JOB_MINUTES = 15


class StaleJobRecoveryService:
    def __init__(self, repository: OrchestratorRepository):
        self._repository = repository

    def recover(self, now: datetime | None = None) -> int:
        reference = now or datetime.now(timezone.utc)
        cutoff = reference - timedelta(minutes=STALE_JOB_MINUTES)
        return self._repository.recover_stale(cutoff)

