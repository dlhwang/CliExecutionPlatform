from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _compose_service_names(compose: str) -> list[str]:
    lines = compose.splitlines()
    start = lines.index("services:") + 1
    end = next(
        index
        for index in range(start, len(lines))
        if lines[index] and not lines[index].startswith(" ")
    )
    return [
        line.strip()[:-1]
        for line in lines[start:end]
        if line.startswith("  ")
        and not line.startswith("    ")
        and line.strip().endswith(":")
    ]


def test_dockerfile_packages_openscad_and_runs_as_non_root():
    dockerfile = _read("Dockerfile")

    assert "FROM python:3.13-slim-bookworm" in dockerfile
    assert "openscad" in dockerfile
    assert "xauth" in dockerfile
    assert "xvfb" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert '"--workers", "1"' in dockerfile
    assert "LLM_API_KEY" not in dockerfile
    assert "DATABASE_URL" not in dockerfile


def test_headless_wrapper_forwards_arguments_without_eval():
    wrapper = _read("docker/openscad-headless")

    assert 'exec xvfb-run -a /usr/bin/openscad "$@"' in wrapper
    assert "eval " not in wrapper


def test_dockerignore_excludes_secrets_and_runtime_data():
    ignored = {
        line.strip()
        for line in _read(".dockerignore").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ".env" in ignored
    assert ".workspaces" in ignored
    assert ".git" in ignored
    assert "venv" in ignored


def test_compose_defines_expected_services():
    compose = _read("docker-compose.yml")

    assert _compose_service_names(compose) == ["db", "app"]
    assert "env_file:" in compose
    assert "./.workspaces:/app/.workspaces" in compose
    assert "healthcheck:" in compose
    assert 'user: "10001:10001"' in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "postgres:16-alpine" in compose
    assert "db:" in compose


def test_env_sample_remains_ascii_only():
    (ROOT / ".env.sample").read_bytes().decode("ascii")
