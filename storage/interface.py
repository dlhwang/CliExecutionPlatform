from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID

class StorageService(ABC):

    @abstractmethod
    def create_directory(self, job_id: UUID, relative_path: str) -> None:
        pass
    
    @abstractmethod
    def create_workspace(self, job_id: UUID) -> None:
        """
        Job을 위한 임시 작업 디렉토리 및 영구 아티팩트 디렉토리를 로컬에 생성합니다.
        - 임시 작업 영역: .workspaces/jobs/{job_id}/
        - 영구 아티팩트 보관 영역: .workspaces/artifacts/{job_id}/
        """
        pass

    @abstractmethod
    def clean_workspace(self, job_id: UUID) -> None:
        """
        Job의 실행이 종료된 후, 임시 작업 공간(.workspaces/jobs/{job_id}/) 전체를 재귀적으로 삭제합니다.
        """
        pass

    @abstractmethod
    def write_file(self, job_id: UUID, relative_path: str, content: str | bytes) -> None:
        """
        임시 작업 공간 내부의 지정된 상대경로에 파일을 기록합니다.
        - Directory Traversal 방지 검증을 반드시 거쳐야 합니다.
        """
        pass

    @abstractmethod
    def read_file(self, job_id: UUID, relative_path: str) -> bytes:
        """
        임시 작업 공간 내의 파일 내용을 바이너리로 읽어옵니다.
        - Directory Traversal 방지 검증이 동반됩니다.
        """
        pass

    @abstractmethod
    def workspace_file_exists(self, job_id: UUID, relative_path: str) -> bool:
        pass

    @abstractmethod
    def workspace_file_size(self, job_id: UUID, relative_path: str) -> int:
        pass

    @abstractmethod
    def copy_workspace_file(
        self,
        source_job_id: UUID,
        target_job_id: UUID,
        relative_path: str,
    ) -> None:
        pass

    @abstractmethod
    def save_artifact(self, job_id: UUID, relative_path: str) -> None:
        """
        임시 작업 공간(.workspaces/jobs/{job_id}/{relative_path})에 생성된 산출물을
        영구 아티팩트 보관소(.workspaces/artifacts/{job_id}/{relative_path})로 복사합니다.
        """
        pass

    @abstractmethod
    def check_artifact_exists(self, job_id: UUID, filename: str) -> bool:
        """
        영구 아티팩트 보관소 내에 특정 파일이 존재하는지 검증합니다.
        """
        pass

    @abstractmethod
    def get_artifact_path(self, job_id: UUID, filename: str) -> Path:
        """
        영구 아티팩트 보관소 내 파일의 물리적 경로를 반환합니다.
        - 상위 경로 침투 검증 필수
        """
        pass
