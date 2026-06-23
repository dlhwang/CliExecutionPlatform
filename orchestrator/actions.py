import os
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from llm.schemas import (
    CreateArtifactAction,
    CreateDirectoryAction,
    RunToolAction,
    WriteFileAction,
)
from runner.service import CLIExecutionRunner
from storage.interface import StorageService


class ActionExecutor:
    def __init__(
        self,
        storage: StorageService,
        runner: CLIExecutionRunner,
        session_factory: Callable[[], Session],
    ):
        self._storage = storage
        self._runner = runner
        self._session_factory = session_factory

    async def execute(self, job_id: UUID, actions) -> None:
        await self.execute_attempt(job_id, actions)

    async def execute_attempt(self, job_id: UUID, actions, on_success=None) -> None:
        token = self._storage.begin_attempt(job_id)
        artifact_actions = []
        db = self._session_factory()
        copied_paths = []
        try:
            for action in actions:
                if isinstance(action, CreateArtifactAction):
                    artifact_actions.append(action)
                    continue
                await self._execute_action(job_id, action)

            from jobs.service import ArtifactService
            artifact_service = ArtifactService(db, self._storage)
            for action in artifact_actions:
                self._storage.save_artifact(job_id, action.path)
                
                # 복사 대상 물리 경로 추적 (Best-Effort Cleanup용)
                base_dir = getattr(self._storage, "base_dir", None)
                if base_dir:
                    copied_path = (base_dir / "artifacts" / str(job_id) / action.path).resolve()
                    copied_paths.append(copied_path)
                
                artifact_service.register_artifact(job_id, action.path)
            db.commit()

            if on_success is not None:
                on_success()
        except Exception:
            db.rollback()
            # Best-Effort Cleanup
            for path in copied_paths:
                try:
                    if path.exists() and path.is_file():
                        os.remove(path)
                except Exception:
                    pass
            self._storage.rollback_attempt(job_id, token)
            raise
        else:
            self._storage.complete_attempt(job_id, token)
        finally:
            db.close()

    async def _execute_action(self, job_id: UUID, action) -> None:
        if isinstance(action, CreateDirectoryAction):
            self._storage.create_directory(job_id, action.path)
        elif isinstance(action, WriteFileAction):
            self._storage.write_file(job_id, action.path, action.content)
        elif isinstance(action, RunToolAction):
            db = self._session_factory()
            try:
                await self._runner.run_tool(job_id, action.tool_name, action.args, db)
            finally:
                db.close()
        else:
            raise ValueError(f"Unsupported retry-boundary action type: {type(action).__name__}")
