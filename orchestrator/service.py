from collections.abc import Callable
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from llm.client import LLMClient, LLMRequest
from llm.parser import ActionPlanParser
from llm.retry import LLMPlanRetryExecutor
from llm.validator import SecurityPolicyValidator
from orchestrator.actions import ActionExecutor
from orchestrator.concurrency import (
    OrchestrationConcurrencyGate,
    OrchestrationQueueTimeoutError,
)
from orchestrator.repository import OrchestratorRepository
from storage.interface import StorageService

logger = logging.getLogger(__name__)

INHERITED_FILES = ("model.scad", "design-spec.md")
ALLOWED_ACTIONS = (
    "CREATE_DIRECTORY",
    "WRITE_FILE",
    "RUN_TOOL",
    "CREATE_ARTIFACT",
)


class JobOrchestratorService:
    def __init__(
        self,
        repository: OrchestratorRepository,
        session_factory: Callable[[], Session],
        storage: StorageService,
        llm_client: LLMClient,
        parser: ActionPlanParser,
        validator: SecurityPolicyValidator,
        action_executor: ActionExecutor,
        concurrency_gate: OrchestrationConcurrencyGate,
    ):
        self._repository = repository
        self._session_factory = session_factory
        self._storage = storage
        self._llm_client = llm_client
        self._parser = parser
        self._validator = validator
        self._action_executor = action_executor
        self._gate = concurrency_gate

    async def run(self, job_id: UUID) -> bool:
        try:
            async with self._gate.slot():
                return await self._run_in_slot(job_id)
        except OrchestrationQueueTimeoutError:
            self._repository.transition(
                job_id,
                ("CREATED",),
                "FAILED",
                "ORCHESTRATION_QUEUE_TIMEOUT",
                "Job exceeded the orchestration queue wait limit.",
            )
            return False

    async def _run_in_slot(self, job_id: UUID) -> bool:
        if not self._repository.transition(
            job_id,
            ("CREATED",),
            "RUNNING",
            "ORCHESTRATION_STARTED",
            "Orchestration started.",
        ):
            return False

        try:
            job = self._repository.get_job(job_id)
            if job is None:
                raise RuntimeError("Job disappeared after orchestration start.")

            context = {}
            if job.parent_job_id is not None:
                for filename in INHERITED_FILES:
                    self._storage.copy_workspace_file(job.parent_job_id, job.id, filename)
                    context[filename] = self._storage.read_file(job.id, filename).decode("utf-8")
                self._repository.append_event(
                    job_id,
                    "REFINEMENT_CONTEXT_COPIED",
                    "Parent design context copied.",
                )

            request = LLMRequest(
                prompt=job.prompt,
                context=context,
                allowed_actions=ALLOWED_ACTIONS,
            )
            retry_executor = LLMPlanRetryExecutor(
                self._llm_client,
                self._parser,
                on_attempt=lambda attempt: self._repository.append_event(
                    job_id,
                    "LLM_ATTEMPT",
                    f"LLM plan request attempt {attempt}.",
                ),
            )
            db = self._session_factory()
            try:
                validation_cb = lambda acts: self._validator.validate_actions(acts, job_id, db)
                async def execution_cb(acts):
                    await self._action_executor.execute_attempt(
                        job_id,
                        acts,
                        on_success=lambda: self._repository.save_action_plan(job_id, acts),
                    )

                actions = await retry_executor.generate_actions(
                    request,
                    validation_cb=validation_cb,
                    execution_cb=execution_cb,
                )
            finally:
                db.close()

            self._repository.append_event(
                job_id,
                "PLAN_EXECUTED",
                "Final action plan validated, executed, and persisted.",
            )
            self._repository.transition(
                job_id,
                ("RUNNING",),
                "COMPLETED",
                "ORCHESTRATION_COMPLETED",
                "Orchestration completed.",
            )
            return True
        except Exception as exc:
            exc_detail = str(exc)
            logger.exception(
                "Orchestration failed for job_id=%s exception_type=%s",
                job_id,
                type(exc).__name__,
            )
            try:
                self._repository.transition(
                    job_id,
                    ("CREATED", "RUNNING"),
                    "FAILED",
                    "ORCHESTRATION_FAILED",
                    f"Orchestration failed: {type(exc).__name__}. Detail: {exc_detail}",
                )
            except Exception:
                logger.exception(
                    "Failed to persist orchestration failure for job_id=%s",
                    job_id,
                )
            return False
