"""
runner/service.py

CLI Runner Service의 핵심 실행 오케스트레이터.

NFR 패턴 구현:
    - Deadline-Enforced Subprocess Pattern (NFR-1.1: 30초 타임아웃)
    - Global Semaphore Guard Pattern (NFR-1.2: 최대 동시 실행 2개)
    - Bounded Backoff Retry Pattern (NFR-1.3: 기동 실패 최대 2회 재시도)
    - Argument Allowlist Validation (NFR-1.4: Shell Injection 차단)
    - Chunked Buffer Accumulation (Q2: 4KB 청크 단위 스트림 수집)
    - Partial Log Preservation (Q4: 타임아웃 시 부분 출력 보존 + TIMEOUT 마커)
"""
import asyncio
import os
import random
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from jobs.models import EventLog
from runner.exceptions import (
    CLIArgumentValidationError,
    CLIExecutionError,
    CLIExecutionLaunchError,
    CLIExecutionTimeoutError,
)
from runner.validator import ArgumentValidator

# ──────────────────────────────────────────────────────────────
# 프로세스 전역 단일 Semaphore (NFR-1.2: 최대 동시 실행 2개)
# 모든 Job의 CLI 실행이 이 단일 Semaphore를 공유합니다 (Q5: Option A).
# ──────────────────────────────────────────────────────────────
_CLI_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(2)

# 재시도 상수 (NFR-1.3)
_MAX_LAUNCH_RETRIES: int = 2
_JITTER_MIN: float = 0.1
_JITTER_MAX: float = 0.5

# 스트림 수집 청크 크기 (Q2: 4KB)
_CHUNK_SIZE: int = 4096

# 기본 타임아웃 (NFR-1.1)
_DEFAULT_TIMEOUT_SECONDS: float = 30.0


class CLIExecutionRunner:
    """
    비동기 서브프로세스 기반 CLI 실행 오케스트레이터.

    사용 예시:
        runner = CLIExecutionRunner()
        exit_code = await runner.run_tool(
            job_id=some_uuid,
            tool_name="openscad",
            args=["-o", "preview.png", "model.scad"],
            db=db_session
        )
    """

    def __init__(self, base_dir: Optional[Path | str] = None) -> None:
        """
        바이너리 경로 및 기본 작업 영역 루트 경로를 초기화합니다.

        Args:
            base_dir: 작업 영역 루트 경로. None이면 프로젝트 루트/.workspaces를 사용합니다.
        """
        # .env / 환경 변수에서 OPENSCAD_BIN_PATH 로드, 없으면 PATH 의존 기본값 사용
        self._openscad_bin: str = os.getenv("OPENSCAD_BIN_PATH", "openscad")

        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent.resolve() / ".workspaces"
        else:
            self.base_dir = Path(base_dir).resolve()

    # ──────────────────────────────────────────────────────────────
    # 공개 인터페이스
    # ──────────────────────────────────────────────────────────────

    async def run_tool(
        self,
        job_id: uuid.UUID,
        tool_name: str,
        args: List[str],
        db: Session,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> int:
        """
        비동기 서브프로세스를 생성하여 CLI 툴을 실행합니다.

        실행 순서:
            1. 인자 Allowlist 검증 (ArgumentValidator)
            2. Semaphore 획득 (최대 2개 동시 실행 보장)
            3. 프로세스 기동 (최대 2회 재시도)
            4. 30초 데드라인 내 스트림 수집 + EventLog INSERT
            5. 종료 코드 검사

        Args:
            job_id: 실행 대상 Job의 UUID (EventLog 외래키)
            tool_name: 호출 도구명 (현재는 "openscad"만 지원)
            args: 도구 실행 인자 리스트 (예: ["-o", "preview.png", "model.scad"])
            db: 동기식 DB 세션 (EventLog 즉시 영속화용)
            timeout_seconds: 프로세스 최대 실행 허용 시간 (기본: 30.0초)

        Returns:
            int: 프로세스의 정상 종료 Exit Code (0)

        Raises:
            CLIArgumentValidationError: Allowlist 검증 실패 시
            CLIExecutionLaunchError: 프로세스 기동 실패 (최대 재시도 초과) 시
            CLIExecutionTimeoutError: 타임아웃 초과 시
            CLIExecutionError: Non-Zero Exit Code로 비정상 종료 시
        """
        # Step 1: Allowlist 인자 검증 (보안: NFR-1.4)
        ArgumentValidator.validate(args)

        # Step 2~5: Semaphore 획득 후 실행 (동시성 제한: NFR-1.2)
        async with _CLI_SEMAPHORE:
            return await self._execute_with_timeout(
                job_id=job_id,
                tool_name=tool_name,
                args=args,
                db=db,
                timeout_seconds=timeout_seconds,
            )

    # ──────────────────────────────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────────────────────────────

    async def _execute_with_timeout(
        self,
        job_id: uuid.UUID,
        tool_name: str,
        args: List[str],
        db: Session,
        timeout_seconds: float,
    ) -> int:
        """30초 데드라인을 감싸는 래퍼. 타임아웃 발생 시 프로세스 강제 종료 및 TIMEOUT 마커 기록."""
        binary = self._openscad_bin
        workspace = self._resolve_job_workspace(job_id)

        # /tmp 임시 디렉토리에서 실행 후 결과를 workspace로 복사
        # - /tmp는 bind mount 권한과 무관하게 항상 쓰기 가능
        # - 실행 완료 후 생성된 파일만 workspace로 복사하여 외부 노출
        with tempfile.TemporaryDirectory(prefix=f"openscad_{job_id}_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            # 1. 실행 전 /tmp에 workspace의 디렉토리 구조 생성 (AC 1)
            for dir_path in workspace.glob("**/"):
                if dir_path.is_dir() and dir_path != workspace:
                    # Path Traversal 방어 검증 (AC 4)
                    if not dir_path.resolve().is_relative_to(workspace.resolve()):
                        raise CLIExecutionLaunchError(
                            message=f"Directory path traversal attempt detected: {dir_path}",
                            target_path=str(dir_path),
                            attempts=0,
                        )
                    rel_dir = dir_path.relative_to(workspace)
                    target_dir = (tmp_path / rel_dir).resolve()
                    if not target_dir.is_relative_to(tmp_path.resolve()):
                        raise CLIExecutionLaunchError(
                            message=f"Directory traversal outside tmp path: {target_dir}",
                            target_path=str(target_dir),
                            attempts=0,
                        )
                    target_dir.mkdir(parents=True, exist_ok=True)

            # 2. CLI 실행에 필요한 입력 파일만 /tmp로 복사 (상대 경로 유지) (AC 2)
            for src_file in workspace.glob("**/*.scad"):
                if src_file.is_file():
                    # Path Traversal 방어 검증 (AC 4)
                    if not src_file.resolve().is_relative_to(workspace.resolve()):
                        raise CLIExecutionLaunchError(
                            message=f"File path traversal attempt detected: {src_file}",
                            target_path=str(src_file),
                            attempts=0,
                        )
                    rel_file = src_file.relative_to(workspace)
                    dest_file = (tmp_path / rel_file).resolve()
                    if not dest_file.is_relative_to(tmp_path.resolve()):
                        raise CLIExecutionLaunchError(
                            message=f"File traversal outside tmp path: {dest_file}",
                            target_path=str(dest_file),
                            attempts=0,
                        )
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)

            # 3. args의 -o 출력 경로를 파싱하여 출력 대상 부모 디렉토리를 /tmp 내부에 생성 (AC 3)
            output_file_path = None
            for idx, arg in enumerate(args):
                if arg == "-o" and idx + 1 < len(args):
                    output_file_path = args[idx + 1]
                    break

            if output_file_path:
                out_path = Path(output_file_path)
                # Path Traversal 방어 검증 (AC 4)
                if out_path.is_absolute() or ".." in out_path.parts:
                    raise CLIArgumentValidationError(offending_arg=output_file_path)
                dest_dir = (tmp_path / out_path.parent).resolve()
                if not dest_dir.is_relative_to(tmp_path.resolve()):
                    raise CLIArgumentValidationError(offending_arg=output_file_path)
                dest_dir.mkdir(parents=True, exist_ok=True)

            # 4. 실행 전 파일 기준 스냅샷(Snapshot) 생성 (AC 5)
            before_snapshot = {}
            for f in tmp_path.glob("**/*"):
                if f.is_file():
                    if not f.resolve().is_relative_to(tmp_path.resolve()):
                        continue
                    rel_f = f.relative_to(tmp_path)
                    stat = f.stat()
                    before_snapshot[rel_f] = (stat.st_size, stat.st_mtime)

            cmd = [binary] + args

            # Step 3: 프로세스 기동 (재시도 포함: NFR-1.3)
            process, attempt_count = await self._launch_with_retry(
                cmd,
                cwd=str(tmp_path),
            )

            # Step 4: 타임아웃 데드라인 + 스트림 수집 (NFR-1.1 + Q2)
            try:
                await asyncio.wait_for(
                    self._collect_streams(process, job_id, db),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                # 타임아웃: 프로세스 강제 종료 (SIGKILL)
                try:
                    process.kill()
                except ProcessLookupError:
                    pass  # 이미 종료된 경우 무시
                await process.wait()  # 좀비 프로세스 방지

                # Q4: 부분 출력 보존 + TIMEOUT 마커 EventLog 기록
                self._write_system_marker(
                    db=db,
                    job_id=job_id,
                    marker_type="TIMEOUT",
                    message=f"[SYSTEM] Process killed: execution exceeded {timeout_seconds}s timeout.",
                )

                raise CLIExecutionTimeoutError(
                    message=f"OpenSCAD tool execution timed out after {timeout_seconds} seconds. Process terminated.",
                    timeout_limit=timeout_seconds,
                )

            # Step 5: Exit Code 검사
            exit_code = process.returncode
            if exit_code != 0:
                raise CLIExecutionError(
                    message=f"OpenSCAD tool execution failed with exit code {exit_code}.",
                    exit_code=exit_code,
                )

            # 5. 실행 전/후 snapshot 비교를 통해 새로 생성되거나 변경된 파일만 workspace에 반영 (AC 5, AC 6)
            for f in tmp_path.glob("**/*"):
                if f.is_file():
                    if not f.resolve().is_relative_to(tmp_path.resolve()):
                        continue
                    rel_f = f.relative_to(tmp_path)
                    
                    stat = f.stat()
                    is_new_or_modified = False
                    if rel_f not in before_snapshot:
                        is_new_or_modified = True
                    else:
                        old_size, old_mtime = before_snapshot[rel_f]
                        if stat.st_size != old_size or stat.st_mtime != old_mtime:
                            is_new_or_modified = True

                    if is_new_or_modified:
                        workspace_target = (workspace / rel_f).resolve()
                        # Path Traversal 방어 검증 (AC 4)
                        if not workspace_target.is_relative_to(workspace.resolve()):
                            raise CLIExecutionError(
                                message=f"Target path traversal attempt during copy: {workspace_target}"
                            )

                        # 기존 파일 충돌 차단 정책 (AC 6)
                        if workspace_target.exists():
                            is_explicit_output = False
                            if output_file_path:
                                explicit_output_path = (workspace / output_file_path).resolve()
                                if workspace_target == explicit_output_path:
                                    is_explicit_output = True

                            if not is_explicit_output:
                                raise CLIExecutionError(
                                    message=f"Access denied: Attempted to overwrite existing non-output file in workspace: {rel_f}"
                                )

                        workspace_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, workspace_target)

        return exit_code

    def _resolve_job_workspace(self, job_id: uuid.UUID) -> Path:
        """Resolve and validate the workspace used as the CLI working directory."""
        jobs_root = (self.base_dir / "jobs").resolve()
        workspace = (jobs_root / str(job_id)).resolve()

        if not workspace.is_relative_to(jobs_root):
            raise CLIExecutionLaunchError(
                message=f"Job workspace is outside the configured jobs root: {workspace}",
                target_path=str(workspace),
                attempts=0,
            )
        if not workspace.is_dir():
            raise CLIExecutionLaunchError(
                message=f"Job workspace does not exist or is not a directory: {workspace}",
                target_path=str(workspace),
                attempts=0,
            )

        return workspace

    async def _launch_with_retry(
        self,
        cmd: List[str],
        cwd: Optional[str],
    ) -> tuple[asyncio.subprocess.Process, int]:
        """
        asyncio.create_subprocess_exec 호출을 OSError 한정으로 최대 2회 재시도합니다.
        (NFR-1.3: Bounded Backoff Retry Pattern)

        Returns:
            (process, attempt_count): 성공한 프로세스 객체와 실제 시도 횟수
        """
        last_error: Optional[OSError] = None

        for attempt in range(_MAX_LAUNCH_RETRIES + 1):
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,  # stdout + stderr 병합
                    cwd=cwd,
                    # shell=False는 asyncio.create_subprocess_exec의 기본값 (NFR-1.4)
                )
                return process, attempt + 1
            except OSError as e:
                last_error = e
                if attempt < _MAX_LAUNCH_RETRIES:
                    # Jitter 백오프: 0.1~0.5초 임의 대기
                    await asyncio.sleep(random.uniform(_JITTER_MIN, _JITTER_MAX))

        # 최대 재시도 초과
        raise CLIExecutionLaunchError(
            message=(
                f"Failed to launch CLI tool after {_MAX_LAUNCH_RETRIES + 1} attempts. "
                f"Last error: {last_error}"
            ),
            target_path=cmd[0],
            attempts=_MAX_LAUNCH_RETRIES + 1,
        ) from last_error

    async def _collect_streams(
        self,
        process: asyncio.subprocess.Process,
        job_id: uuid.UUID,
        db: Session,
    ) -> None:
        """
        프로세스 stdout(stderr 병합)을 4KB 청크 단위로 수집하여 EventLog에 INSERT합니다.
        (Q2: Chunked Buffer Accumulation Pattern)

        - 4KB 청크 단위로 읽어 줄(line) 단위로 분할합니다.
        - 청크 경계에서 잘린 부분 줄(partial line)은 line_buffer에 유지합니다.
        - 각 청크 완성 시 DB에 일괄 INSERT합니다.
        """
        line_buffer: bytes = b""

        assert process.stdout is not None, "stdout pipe was not configured"

        while True:
            chunk = await process.stdout.read(_CHUNK_SIZE)
            if not chunk:
                break

            line_buffer += chunk
            # 줄 단위 분할
            raw_lines = line_buffer.split(b"\n")
            line_buffer = raw_lines[-1]  # 마지막 미완성 줄 보존
            complete_lines = raw_lines[:-1]

            if complete_lines:
                records = [
                    EventLog(
                        job_id=job_id,
                        event_type="CLI_OUTPUT",
                        message=line.decode("utf-8", errors="replace").rstrip("\r"),
                    )
                    for line in complete_lines
                    if line  # 빈 줄 제외
                ]
                if records:
                    db.add_all(records)
                    db.commit()

        # 루프 종료 후 잔여 버퍼 처리 (마지막 줄이 개행 없이 끝난 경우)
        if line_buffer:
            remainder = line_buffer.decode("utf-8", errors="replace").rstrip("\r")
            if remainder:
                db.add(
                    EventLog(
                        job_id=job_id,
                        event_type="CLI_OUTPUT",
                        message=remainder,
                    )
                )
                db.commit()

        # 프로세스 종료 대기
        await process.wait()

    def _write_system_marker(
        self,
        db: Session,
        job_id: uuid.UUID,
        marker_type: str,
        message: str,
    ) -> None:
        """
        시스템 이벤트 마커 레코드를 event_type="SYSTEM_EVENT"로 EventLog에 기록합니다.
        (Q4: Partial Log Preservation — TIMEOUT 마커 포함)

        Args:
            db: 동기식 DB 세션
            job_id: 실행 중인 Job의 UUID
            marker_type: 마커 유형 식별자 ("TIMEOUT", "LAUNCH_FAILED", "COMPLETE" 등)
            message: 마커 메시지 내용
        """
        db.add(
            EventLog(
                job_id=job_id,
                event_type="SYSTEM_EVENT",
                message=f"[{marker_type}] {message}",
            )
        )
        db.commit()
