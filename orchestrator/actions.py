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
        for action in actions:
            if isinstance(action, CreateDirectoryAction):
                self._storage.create_directory(job_id, action.path)
            elif isinstance(action, WriteFileAction):
                self._storage.write_file(job_id, action.path, action.content)
            elif isinstance(action, RunToolAction):
                db = self._session_factory()
                try:
                    await self._runner.run_tool(
                        job_id,
                        action.tool_name,
                        action.args,
                        db,
                    )
                finally:
                    db.close()
            elif isinstance(action, CreateArtifactAction):
                self._storage.save_artifact(job_id, action.path)
            else:
                raise ValueError(f"Unsupported action type: {type(action).__name__}")

