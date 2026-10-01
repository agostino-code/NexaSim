"""
Integration and validation tests for Docker and Docker Compose environment in NexaSim.
Covers Dockerfile multi-stage builds, docker-compose configuration, volume persistence,
and container execution of OMNeT++, SUMO, Conan 2, and the simulation runner.
"""

import os
import shutil
import subprocess
import pytest
import yaml

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
    """Validates Dockerfile syntax, multi-stage targets, and environment settings."""

    def test_dockerfile_exists(self):
        assert os.path.isfile(DOCKERFILE_PATH), "Dockerfile must exist at repository root"

    def test_dockerfile_multistage_targets(self):
        with open(DOCKERFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        required_stages = [
            "FROM debian:${TAG} AS base",
            "FROM base AS base-gui",
            "FROM base AS build-headless",
            "FROM base-gui AS build-gui",
            "FROM base AS headless",
            "FROM base-gui AS final",
        ]
        for stage in required_stages:
            assert stage in content, f"Missing expected Dockerfile stage: '{stage}'"

    def test_dockerfile_environment_vars(self):
        with open(DOCKERFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        assert "ENV OMNETPP_ROOT=/omnetpp" in content
        assert "ENV SUMO_HOME=/usr/local/share/sumo" in content
        assert "ENV PATH=/omnetpp/bin:$PATH" in content
        assert "ENV DISPLAY=:99" in content

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
            "nexasim-build",
            "nexasim",
            "nexasim-scenario",
            "nexasim-analyze",
            "nexasim-gui",
        ]
        for s in expected_services:
            assert s in services, f"Expected service '{s}' missing in docker-compose.yml"

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

    def test_docker_compose_gui_ports(self):
        with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        gui_svc = data.get("services", {}).get("nexasim-gui", {})
        ports = gui_svc.get("ports", [])
        assert any("6080" in str(p) for p in ports), "nexasim-gui must expose port 6080 for NoVNC"


class TestDockerLiveIntegration:
    """Tests executing commands inside Docker containers via docker compose."""

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

    def test_container_opp_run_simulation_execution(self):
        if not is_docker_daemon_running():
            pytest.skip("Docker daemon is not accessible in this environment")
        cmd = [
            "docker", "compose", "run", "--rm", "nexasim",
            "bash", "-c",
            "./tools/opp_run.sh -f scenarios/generated/stelvio/omnetpp.ini -u Cmdenv --sim-time-limit=0.5s"
        ]
        res = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert res.returncode == 0, f"Simulation runner failed in container:\n{res.stderr}\n{res.stdout}"
        combined = res.stdout + res.stderr
        assert "Simulation time limit reached" in combined, "Simulation should reach time limit cleanly"
        assert "Setting up network" in combined
