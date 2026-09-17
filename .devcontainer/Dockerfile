# NexaSim Dev Container Dockerfile
# Provides OMNeT++ 5.6.2 (with Qtenv GUI), SUMO 1.21.0 (with sumo-gui), Conan 2, Ninja, and CMake

ARG TAG=bookworm
FROM debian:${TAG} AS setup
SHELL [ "/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash-completion bison build-essential cmake flex git git-lfs python3 python3-pip \
    libboost-all-dev libcrypto++-dev libfox-1.6-dev libgdal-dev libgeographiclib-dev \
    libopenscenegraph-dev libproj-dev libqt5opengl5-dev libqt5svg5-dev libxerces-c-dev \
    ninja-build qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools sudo pkg-config libzmq5-dev libprotobuf-dev \
    protobuf-compiler curl x11-apps \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages conan pyyaml matplotlib

###############
# Build stage #
###############

FROM setup AS build

ARG SUMO_TAG=v1_21_0
ARG OMNETPP_TAG=omnetpp-5.6.2

# Build OMNeT++ with Qtenv GUI support
RUN git clone --recurse --depth 1 --branch ${OMNETPP_TAG} https://github.com/omnetpp/omnetpp
WORKDIR /omnetpp
RUN mv configure.user.dist configure.user
RUN source setenv -f && ./configure WITH_OSGEARTH=no WITH_QTENV=yes && make -j$(nproc --all)

# Build SUMO with GUI support
WORKDIR /
RUN git clone --recurse --depth 1 --branch ${SUMO_TAG} https://github.com/eclipse-sumo/sumo
WORKDIR /sumo
RUN cmake -B build . -G Ninja -DCMAKE_INSTALL_PREFIX=/sumo-prefix && cmake --build build --parallel $(nproc --all) && cmake --install build

######################
# Installation stage #
######################

FROM setup AS final

ARG USER=devcontainer

COPY --from=build /omnetpp/bin /omnetpp/bin
COPY --from=build /omnetpp/include /omnetpp/include
COPY --from=build /omnetpp/lib /omnetpp/lib
COPY --from=build /omnetpp/images /omnetpp/images
COPY --from=build /omnetpp/Makefile.inc /omnetpp

COPY --from=build /sumo-prefix/ /usr/local

RUN useradd -m -s /bin/bash -G sudo ${USER}
RUN echo "${USER} ALL=(ALL:ALL) NOPASSWD: ALL" | tee /etc/sudoers.d/${USER}
RUN chmod 755 /root

USER ${USER}
WORKDIR /workspace

ENV PATH=/omnetpp/bin:$PATH
ENV OMNETPP_ROOT=/omnetpp
ENV SUMO_HOME=/usr/local/share/sumo
