"""
Integration and validation tests for Docker and Docker Compose environment in NexaSim.
Covers Dockerfile multi-stage builds, docker-compose configuration, volume persistence,
intelligent execution backend resolution (Native vs Warm docker exec vs Cold run),
and container execution of OMNeT++, SUMO, Conan 2, and the simulation runner.
"""

import os
import shutil
import subprocess
from unittest.mock import patch
import pytest
import yaml

from tools.nexasim import resolve_execution_backend, find_warm_container

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCKERFILE_PATH = os.path.join(REPO_ROOT, "Dockerfile")
COMPOSE_PATH = os.path.join(REPO_ROOT, "docker-compose.yml")


def is_docker_cli_available() -> bool:
    """Check if docker CLI is available in PATH."""
    return shutil.which("docker") is not None


def is_docker_daemon_running() -> bool:
    """Check if docker command can communicate with running daemon."""
    if not is_docker_cli_available():
        return False
    try:
        res = subprocess.run(
            ["docker", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return res.returncode == 0
    except Exception:
        return False


class TestDockerfileStructure:
    """Validates Dockerfile syntax, multi-stage targets, BuildKit caching, and environment settings."""

    def test_dockerfile_exists(self):
        assert os.path.isfile(DOCKERFILE_PATH), "Dockerfile must exist at repository root"

    def test_dockerfile_multistage_targets(self):
        with open(DOCKERFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        required_stages = [
            "FROM node:20-alpine AS frontend-build",
            "FROM debian:${TAG} AS sim-builder",
            "FROM debian:${TAG} AS runtime",
            "FROM runtime AS headless",
            "FROM sim-builder AS devcontainer",
        ]
        for stage in required_stages:
            assert stage in content, f"Missing expected Dockerfile stage: '{stage}'"

    def test_dockerfile_buildkit_cache_mounts(self):
        with open(DOCKERFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        assert "--mount=type=cache,target=/var/cache/apt" in content
        assert "--mount=type=cache,target=/root/.cache/ccache" in content

    def test_dockerfile_environment_vars(self):
        with open(DOCKERFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        assert "ENV OMNETPP_ROOT=/omnetpp" in content
        assert "ENV SUMO_HOME=/usr/local/share/sumo" in content
        assert "ENV PATH=/omnetpp/bin:/usr/local/bin:$PATH" in content
        assert "ENV CONAN_HOME=/root/.conan2" in content
        assert "ENV PYTHONUNBUFFERED=1" in content

    def test_dockerfile_python_dependencies(self):
        with open(DOCKERFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        assert "conan" in content
        assert "fastapi" in content
        assert "uvicorn" in content
        assert "pyyaml" in content


class TestDockerComposeConfig:
    """Validates docker-compose.yml structure, services, mounts, and dependencies."""

    def test_docker_compose_exists(self):
        assert os.path.isfile(COMPOSE_PATH), "docker-compose.yml must exist at repository root"

    def test_docker_compose_valid_yaml(self):
        with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert isinstance(data, dict), "docker-compose.yml must parse to a dict"
        assert "services" in data, "services key must be defined in docker-compose.yml"
        assert "volumes" in data, "volumes key must be defined in docker-compose.yml"

    def test_docker_compose_services_defined(self):
        with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        services = data.get("services", {})
        expected_services = [
            "nexasim-studio",
            "nexasim-build",
            "nexasim",
            "nexasim-scenario",
            "nexasim-analyze",
        ]
        for s in expected_services:
            assert s in services, f"Expected service '{s}' missing in docker-compose.yml"

    def test_docker_compose_studio_service(self):
        with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        studio = data.get("services", {}).get("nexasim-studio", {})
        assert studio.get("build", {}).get("target") == "runtime"
        assert studio.get("container_name") == "nexasim-studio"
        ports = studio.get("ports", [])
        assert any("8000:8000" in str(p) for p in ports)
        volumes = studio.get("volumes", [])
        assert any("./scenarios:/artery/scenarios" in str(v) for v in volumes)

    def test_docker_compose_volumes_and_conan_cache(self):
        with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        volumes = data.get("volumes", {})
        assert "artery-conan2-cache" in volumes, "artery-conan2-cache named volume must be declared"
        assert "artery-build-cache" in volumes, "artery-build-cache named volume must be declared"

        services = data.get("services", {})
        nexasim = services.get("nexasim", {})
        env = nexasim.get("environment", [])
        assert "CONAN_HOME=/root/.conan2" in env or any(
            "CONAN_HOME" in str(e) for e in env
        ), "CONAN_HOME must be set to /root/.conan2"


class TestExecutionBackendResolution:
    """Verifies intelligent detection and routing across Native, Warm docker exec, and Cold docker run."""

    def test_resolve_backend_native_inside_docker(self):
        """Inside container: resolves to Priority 1 Native execution directly with opp_run.sh."""
        with patch("tools.nexasim.is_inside_docker", return_value=True):
            backend, cmd, cwd, env = resolve_execution_backend("stelvio")
            assert backend == "native"
            assert cmd[0] == "bash"
            assert any("opp_run.sh" in arg for arg in cmd)
            assert "-u" in cmd and "Cmdenv" in cmd
            assert "stelvio" in cwd

    def test_resolve_backend_warm_container_exec(self):
        """Host with running container: resolves to Priority 2 Warm Container via docker exec (<50ms)."""
        with patch("tools.nexasim.is_inside_docker", return_value=False), \
             patch("tools.nexasim.find_warm_container", return_value="nexasim-studio"):
            backend, cmd, cwd, env = resolve_execution_backend("stelvio")
            assert backend == "docker_exec"
            assert cmd[0] == "docker"
            assert cmd[1] == "exec"
            assert "nexasim-studio" in cmd
            assert any("opp_run.sh" in arg for arg in cmd)

    def test_resolve_backend_cold_docker_run_fallback(self):
        """Host without running container: resolves to Priority 3 Cold docker compose run fallback."""
        with patch("tools.nexasim.is_inside_docker", return_value=False), \
             patch("tools.nexasim.find_warm_container", return_value=None):
            backend, cmd, cwd, env = resolve_execution_backend("stelvio")
            assert backend == "docker_run"
            assert cmd[0] == "docker"
            assert "compose" in cmd
            assert "run" in cmd
            assert "--rm" in cmd
            assert any("opp_run.sh" in arg for arg in cmd)


class TestDockerLiveIntegration:
    """Tests executing commands inside Docker containers via docker compose when daemon is active."""

    def test_docker_compose_config_validation(self):
        if not is_docker_cli_available():
            pytest.skip("Docker CLI is not available in PATH")
        res = subprocess.run(
            ["docker", "compose", "config"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert res.returncode == 0, f"docker compose config failed:\n{res.stderr}"

    def test_container_toolchain_versions(self):
        if not is_docker_daemon_running():
            pytest.skip("Docker daemon is not accessible in this environment")

        # Skip live container run if image is not pre-built locally (avoids 20min build in unit test)
        res_img = subprocess.run(
            ["docker", "image", "inspect", "artery-nexasim"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if res_img.returncode != 0:
            res_img2 = subprocess.run(
                ["docker", "image", "inspect", "nexasim"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res_img2.returncode != 0:
                pytest.skip("NexaSim image not pre-built locally; run 'docker compose build' to test live container execution")

        cmd = [
            "docker", "compose", "run", "--rm", "nexasim",
            "bash", "-c",
            "opp_run -v && sumo --version && conan --version && python3 --version"
        ]
        res = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert res.returncode == 0, f"Toolchain check failed inside container:\n{res.stderr}"
        output = res.stdout + res.stderr
        assert "OMNeT++" in output or "opp_run" in output, "OMNeT++ must be available"
        assert "Eclipse SUMO" in output or "sumo" in output, "SUMO must be available"
        assert "Conan version 2" in output, "Conan 2.x must be installed"
        assert "Python 3." in output, "Python 3 must be available"
