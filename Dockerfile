# ==============================================================================
# NexaSim 3D Unified Simulator (Horizon Europe NexaSphere)
# High-Performance Headless Multi-Stage Build
# ==============================================================================

ARG TAG=bookworm-slim

# ==============================================================================
# Stage 1: Frontend Build (NexaSim Studio React 18 + TypeScript + Vite)
# ==============================================================================
FROM node:20-alpine AS frontend-build
WORKDIR /studio

# Cache package dependencies
COPY studio/package*.json ./
RUN npm ci || npm install

# Build production assets
COPY studio/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Simulation Builder (OMNeT++ Headless, SUMO, Conan 2, NexaSim C++)
# ==============================================================================
FROM debian:${TAG} AS sim-builder
SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies with BuildKit cache mounts
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    bison build-essential ccache cmake flex git \
    libfox-1.6-dev libgdal-dev libgeographiclib-dev libproj-dev \
    libprotobuf-dev libxerces-c-dev libxml2-dev libzmq5-dev \
    ninja-build pkg-config protobuf-compiler python3-dev \
    python3-pip python3-venv wget zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Conan 2.x and Python tools
RUN pip3 install --no-cache-dir --break-system-packages conan pyyaml

# Build SUMO Headless (no GUI, no Qt, no OSG)
ARG SUMO_TAG=v1_21_0
RUN git clone --recurse --depth 1 --branch ${SUMO_TAG} https://github.com/eclipse-sumo/sumo /sumo \
    && cd /sumo \
    && cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/sumo-prefix \
        -DENABLE_CS_BINDINGS=OFF \
        -DENABLE_JAVA_BINDINGS=OFF \
        -DENABLE_PYTHON_BINDINGS=OFF \
        -DENABLE_GUI=OFF \
        -DNETEDIT=OFF \
    && cmake --build build --parallel $(nproc) \
    && cmake --install build \
    && rm -rf /sumo

# Build OMNeT++ Headless Release
ARG OMNETPP_TAG=omnetpp-5.7.1
RUN git clone --recurse --depth 1 --branch ${OMNETPP_TAG} https://github.com/omnetpp/omnetpp /omnetpp \
    && cd /omnetpp \
    && cp configure.user.dist configure.user \
    && source ./setenv -f \
    && ./configure WITH_QTENV=no WITH_OSG=no WITH_OSGEARTH=no \
    && make -j$(nproc) MODE=release \
    && rm -rf out test samples doc

# Setup NexaSim workspace and compile C++ binaries with Ninja & ccache
WORKDIR /artery
COPY recipes /artery/recipes
COPY conanfile.py conandata.yml /artery/
RUN --mount=type=cache,target=/root/.cache/ccache \
    conan export recipes/inet --version 4.2.2 \
    && conan export recipes/space_veins --version 0.3 \
    && conan export recipes/simu5g --version 1.1.0 \
    && conan export recipes/vanetza --version 26.02 \
    && conan profile detect --force \
    && conan install . --build=missing -s build_type=Release

COPY CMakeLists.txt /artery/
COPY cmake /artery/cmake
COPY src /artery/src
COPY scenarios /artery/scenarios
RUN --mount=type=cache,target=/root/.cache/ccache \
    cmake -S . -B build/Release -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_FLAGS="-O3 -DNDEBUG -mtune=generic" \
        -DCMAKE_TOOLCHAIN_FILE=/artery/build/Release/generators/conan_toolchain.cmake \
        -DOMNETPP_ROOT=/omnetpp \
    && cmake --build build/Release --parallel $(nproc)

# ==============================================================================
# Stage 3: Lightweight Runtime (< 500 MB, Headless, Native-First)
# ==============================================================================
FROM debian:${TAG} AS runtime
SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# Minimal shared libraries only (no compilers, no Qt5, no OSG, no X11)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl \
    libfox-1.6-0 libgdal32 libgeographiclib23 libproj25 \
    libprotobuf32 libxerces-c3.2 libxml2 libzmq5 zlib1g \
    procps python3 python3-pip python3-venv \
    && pip3 install --no-cache-dir --break-system-packages \
        fastapi uvicorn pydantic pyyaml websockets httpx \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# OMNeT++ headless runtime
COPY --from=sim-builder /omnetpp/bin /omnetpp/bin
COPY --from=sim-builder /omnetpp/lib /omnetpp/lib
COPY --from=sim-builder /omnetpp/include /omnetpp/include
COPY --from=sim-builder /omnetpp/images /omnetpp/images
COPY --from=sim-builder /omnetpp/Makefile.inc /omnetpp/Makefile.inc

# SUMO headless runtime
COPY --from=sim-builder /sumo-prefix/ /usr/local/

# NexaSim build artifacts and Conan packages
COPY --from=sim-builder /root/.conan2 /root/.conan2
COPY --from=sim-builder /artery/build /artery/build

# React 18 Studio frontend
COPY --from=frontend-build /studio/dist /artery/studio/dist

# Application source, configs and simulation tools
WORKDIR /artery
COPY src /artery/src
COPY scenarios /artery/scenarios
COPY config /artery/config
COPY tools /artery/tools
COPY recipes /artery/recipes
COPY CMakeLists.txt conanfile.py conandata.yml /artery/

ENV OMNETPP_ROOT=/omnetpp
ENV PATH=/omnetpp/bin:/usr/local/bin:$PATH
ENV SUMO_HOME=/usr/local/share/sumo
ENV CONAN_HOME=/root/.conan2
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python3", "tools/studio.py", "--host", "0.0.0.0", "--port", "8000"]

# Backward-compatibility alias
FROM runtime AS headless

# ==============================================================================
# Stage 4: DevContainer (Full Toolchain for Interactive Development)
# ==============================================================================
FROM sim-builder AS devcontainer
ARG USER=devcontainer
RUN apt-get update && apt-get install -y --no-install-recommends sudo \
    && useradd -m -s /bin/bash -G sudo ${USER} \
    && echo "${USER} ALL=(ALL:ALL) NOPASSWD: ALL" | tee /etc/sudoers.d/${USER} \
    && chmod 755 /root \
    && rm -rf /var/lib/apt/lists/*

USER ${USER}
WORKDIR /artery
ENV PATH=/omnetpp/bin:$PATH
ENV OMNETPP_ROOT=/omnetpp
ENV SUMO_HOME=/usr/local/share/sumo
