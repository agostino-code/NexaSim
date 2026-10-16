# NexaSim Dev Container Dockerfile
# Reuses the sim-builder stage defined in the root Dockerfile
# When using VS Code, .devcontainer/devcontainer.json specifies:
#   "dockerfile": "../Dockerfile", "target": "devcontainer"

ARG TAG=bookworm-slim
FROM sim-builder AS devcontainer

ARG USER=devcontainer
RUN apt-get update && apt-get install -y --no-install-recommends sudo \
    && useradd -m -s /bin/bash -G sudo ${USER} 2>/dev/null || true \
    && echo "${USER} ALL=(ALL:ALL) NOPASSWD: ALL" | tee /etc/sudoers.d/${USER} \
    && chmod 755 /root \
    && rm -rf /var/lib/apt/lists/*

USER ${USER}
WORKDIR /workspace

ENV PATH=/omnetpp/bin:$PATH
ENV OMNETPP_ROOT=/omnetpp
ENV SUMO_HOME=/usr/local/share/sumo
