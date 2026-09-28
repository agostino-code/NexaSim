# NexaSim 3D Unified Simulator (Horizon Europe NexaSphere)
# Supports both High-Performance Headless (Cmdenv) and Interactive Web-based GUI (Qtenv + NoVNC)

# Distribution tag
ARG TAG=bookworm-slim

# ==============================================================================
# 1. BASE: Core dependencies (No GUI, No X11, No Qt)
# ==============================================================================
FROM debian:${TAG} AS base
SHELL [ "/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bison build-essential flex git python3-dev \
    libxml2-dev wget zlib1g-dev cmake \
    libfox-1.6-dev libgdal-dev libproj-dev \
    libxerces-c-dev ninja-build curl python3-venv \
    clang-tidy pkg-config libzmq5-dev \
    libprotobuf-dev protobuf-compiler python3-pip \
    && pip3 install --no-cache-dir --break-system-packages conan fastapi uvicorn python-dotenv pyyaml \
    && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# 2. GUI-DEPS: Adds GUI libraries
# ==============================================================================
FROM base AS base-gui
RUN apt-get update && apt-get install -y --no-install-recommends \
    qtbase5-dev qtdeclarative5-dev \
    libqt5opengl5-dev libqt5svg5-dev \
    xvfb x11vnc fluxbox novnc websockify \
    && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# 3. BUILDER: SUMO & OMNeT++ Headless
# ==============================================================================
FROM base AS build-headless
ARG SUMO_TAG=v1_21_0

RUN git clone --recurse --depth 1 --branch ${SUMO_TAG} https://github.com/eclipse-sumo/sumo
WORKDIR /sumo
RUN cmake -B build -G Ninja \
    -DCMAKE_BUILD_CONFIG=Release \
    -DCMAKE_INSTALL_PREFIX=/sumo-prefix \
    -DENABLE_CS_BINDINGS=OFF \
    -DENABLE_JAVA_BINDINGS=OFF \
    -DENABLE_PYTHON_BINDINGS=OFF \
    -DNETEDIT=OFF \
    && cmake --build build --parallel $(nproc --all) \
    && cmake --install build

WORKDIR /
ARG OMNETPP_TAG=omnetpp-5.7.1
RUN git clone --recurse --depth 1 --branch ${OMNETPP_TAG} https://github.com/omnetpp/omnetpp /omnetpp
WORKDIR /omnetpp
RUN if [ -f configure.user.dist ]; then cp configure.user.dist configure.user; fi \
    && source ./setenv -f \
    && ./configure WITH_QTENV=no WITH_OSG=no WITH_OSGEARTH=no \
    && make -j$(nproc --all) MODE=release

# ==============================================================================
# 4. BUILDER: OMNeT++ with GUI
# ==============================================================================
FROM base-gui AS build-gui
ARG OMNETPP_TAG=omnetpp-5.7.1

WORKDIR /
RUN git clone --recurse --depth 1 --branch ${OMNETPP_TAG} https://github.com/omnetpp/omnetpp /omnetpp
WORKDIR /omnetpp
RUN if [ -f configure.user.dist ]; then cp configure.user.dist configure.user; fi \
    && source ./setenv -f \
    && ./configure WITH_QTENV=yes WITH_OSG=no WITH_OSGEARTH=no \
    && make -j$(nproc --all) MODE=release

# ==============================================================================
# 5. HEADLESS (Final ultra-thin image)
# ==============================================================================
FROM base AS headless

COPY --from=build-headless /omnetpp/bin /omnetpp/bin
COPY --from=build-headless /omnetpp/include /omnetpp/include
COPY --from=build-headless /omnetpp/lib /omnetpp/lib
COPY --from=build-headless /omnetpp/images /omnetpp/images
COPY --from=build-headless /omnetpp/Makefile.inc /omnetpp

COPY --from=build-headless /sumo-prefix/ /usr/local

RUN cd /usr/local/bin && \
    (curl -sSL --retry 5 --retry-connrefused -O https://raw.githubusercontent.com/llvm/llvm-project/main/clang-tools-extra/clang-tidy/tool/clang-tidy-diff.py || true) && \
    if [ -f clang-tidy-diff.py ]; then chmod +x clang-tidy-diff.py; fi

ENV PATH=/omnetpp/bin:$PATH
ENV OMNETPP_ROOT=/omnetpp
ENV SUMO_HOME=/usr/local/share/sumo

# ==============================================================================
# 6. GUI (Final fat image with Qtenv & NoVNC)
# ==============================================================================
FROM base-gui AS final

COPY --from=build-gui /omnetpp/bin /omnetpp/bin
COPY --from=build-gui /omnetpp/include /omnetpp/include
COPY --from=build-gui /omnetpp/lib /omnetpp/lib
COPY --from=build-gui /omnetpp/images /omnetpp/images
COPY --from=build-gui /omnetpp/Makefile.inc /omnetpp

COPY --from=build-headless /sumo-prefix/ /usr/local

RUN cd /usr/local/bin && \
    (curl -sSL --retry 5 --retry-connrefused -O https://raw.githubusercontent.com/llvm/llvm-project/main/clang-tools-extra/clang-tidy/tool/clang-tidy-diff.py || true) && \
    if [ -f clang-tidy-diff.py ]; then chmod +x clang-tidy-diff.py; fi

ENV PATH=/omnetpp/bin:$PATH
ENV OMNETPP_ROOT=/omnetpp
ENV SUMO_HOME=/usr/local/share/sumo
ENV DISPLAY=:99