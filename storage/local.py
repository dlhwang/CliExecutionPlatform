import shutil
import uuid
from pathlib import Path
from uuid import UUID
from storage.interface import StorageService

class LocalStorageService(StorageService):
    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            # 기본값: 프로젝트 루트/.workspaces
            self.base_dir = Path(__file__).parent.parent.resolve() / ".workspaces"
        else:
            self.base_dir = Path(base_dir).resolve()
        
        # 기본 디렉토리 생성
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate_safe_path(self, job_id: UUID, relative_path: str, dir_type: str = "jobs") -> Path:
        """
        상대경로 내 Directory Traversal 시도를 엄격하게 차단하고 물리 경로를 반환합니다.
        """
        # 1. 1차적인 경로 탐색 문자열 검사
        if "../" in relative_path or "..\\" in relative_path or relative_path.startswith("/") or relative_path.startswith("\\"):
            raise PermissionError("Access Denied: Path traversal attempt detected.")

        # 2. 지정된 Job의 기본 디렉토리 (jobs/{job_id}/ 또는 artifacts/{job_id}/)
        base_job_dir = (self.base_dir / dir_type / str(job_id)).resolve()
        
        # 3. 최종 경로 결합 및 resolve
        target_path = (base_job_dir / relative_path).resolve()
        
        # 4. 최종 경로가 기본 디렉토리의 하위에 위치하는지 확인
        if not target_path.is_relative_to(base_job_dir):
            raise PermissionError("Access Denied: Path traversal attempt detected.")
            
        return target_path

    def create_workspace(self, job_id: UUID) -> None:
        jobs_dir = self.base_dir / "jobs" / str(job_id)
        artifacts_dir = self.base_dir / "artifacts" / str(job_id)
        
        jobs_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

    def create_directory(self, job_id: UUID, relative_path: str) -> None:
        self._validate_safe_path(job_id, relative_path, "jobs").mkdir(
            parents=True, exist_ok=True
        )

    def clean_workspace(self, job_id: UUID) -> None:
        jobs_dir = self.base_dir / "jobs" / str(job_id)
        if jobs_dir.exists() and jobs_dir.is_dir():
            shutil.rmtree(jobs_dir)

    def write_file(self, job_id: UUID, relative_path: str, content: str | bytes) -> None:
        target_path = self._validate_safe_path(job_id, relative_path, "jobs")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, str):
            target_path.write_text(content, encoding="utf-8")
        else:
            target_path.write_bytes(content)

    def read_file(self, job_id: UUID, relative_path: str) -> bytes:
        target_path = self._validate_safe_path(job_id, relative_path, "jobs")
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"File not found: {relative_path} in workspace of job {job_id}")
        return target_path.read_bytes()

    def workspace_file_exists(self, job_id: UUID, relative_path: str) -> bool:
        try:
            target_path = self._validate_safe_path(job_id, relative_path, "jobs")
            return target_path.is_file()
        except PermissionError:
            return False

    def workspace_file_size(self, job_id: UUID, relative_path: str) -> int:
        target_path = self._validate_safe_path(job_id, relative_path, "jobs")
        if not target_path.is_file():
            raise FileNotFoundError(f"File not found: {relative_path} in workspace of job {job_id}")
        return target_path.stat().st_size

    def copy_workspace_file(
        self,
        source_job_id: UUID,
        target_job_id: UUID,
        relative_path: str,
    ) -> None:
        source = self._validate_safe_path(source_job_id, relative_path, "jobs")
        if not source.is_file():
            raise FileNotFoundError(
                f"File not found: {relative_path} in workspace of job {source_job_id}"
            )
        target = self._validate_safe_path(target_job_id, relative_path, "jobs")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    def save_artifact(self, job_id: UUID, relative_path: str) -> None:
        # jobs/ 디렉토리 내 원본 파일
        src_path = self._validate_safe_path(job_id, relative_path, "jobs")
        if not src_path.exists() or not src_path.is_file():
            raise FileNotFoundError(f"Source file not found for artifact: {relative_path} in job {job_id}")
            
        # artifacts/ 디렉토리 내 타겟 파일
        dest_path = self._validate_safe_path(job_id, relative_path, "artifacts")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copyfile(src_path, dest_path)

    def check_artifact_exists(self, job_id: UUID, filename: str) -> bool:
        try:
            target_path = self._validate_safe_path(job_id, filename, "artifacts")
            return target_path.exists() and target_path.is_file()
        except PermissionError:
            return False

    def get_artifact_path(self, job_id: UUID, filename: str) -> Path:
        target_path = self._validate_safe_path(job_id, filename, "artifacts")
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"Artifact not found: {filename} for job {job_id}")
        return target_path

    @staticmethod
    def _copy_tree_with_copyfile(source: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            return
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            destination = target / relative
            if path.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)

    def _attempt_path(self, job_id: UUID, token: str) -> Path:
        snapshots_root = (self.base_dir / ".attempt-snapshots" / str(job_id)).resolve()
        snapshot = (snapshots_root / token).resolve()
        if not snapshot.is_relative_to(snapshots_root):
            raise PermissionError("Access Denied: Invalid attempt snapshot token.")
        return snapshot

    def begin_attempt(self, job_id: UUID) -> str:
        token = str(uuid.uuid4())
        snapshot = self._attempt_path(job_id, token)
        self._copy_tree_with_copyfile(
            self.base_dir / "jobs" / str(job_id), snapshot / "jobs"
        )
        self._copy_tree_with_copyfile(
            self.base_dir / "artifacts" / str(job_id), snapshot / "artifacts"
        )
        return token

    def rollback_attempt(self, job_id: UUID, token: str) -> None:
        snapshot = self._attempt_path(job_id, token)
        if not snapshot.is_dir():
            raise FileNotFoundError(f"Attempt snapshot not found: {token}")
        for dir_type in ("jobs", "artifacts"):
            destination = self.base_dir / dir_type / str(job_id)
            if destination.exists():
                shutil.rmtree(destination)
            self._copy_tree_with_copyfile(snapshot / dir_type, destination)
        self.complete_attempt(job_id, token)

    def complete_attempt(self, job_id: UUID, token: str) -> None:
        snapshot = self._attempt_path(job_id, token)
        if snapshot.exists():
            shutil.rmtree(snapshot)
