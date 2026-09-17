#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Ensure bidirectional compatibility between /root/.conan2 and /home/devcontainer/.conan2
if [ -d /home/devcontainer/.conan2 ] && [ ! -e /root/.conan2 ]; then
    sudo mkdir -p /root 2>/dev/null || true
    sudo chmod 755 /root 2>/dev/null || true
    sudo ln -sfn /home/devcontainer/.conan2 /root/.conan2 2>/dev/null || true
fi
if [ -d /root/.conan2 ] && [ ! -e /home/devcontainer/.conan2 ]; then
    sudo mkdir -p /home/devcontainer 2>/dev/null || true
    sudo ln -sfn /root/.conan2 /home/devcontainer/.conan2 2>/dev/null || true
fi

# Ensure root Conan cache is accessible if present
if [ -d /root/.conan2 ]; then
    sudo chmod 755 /root /root/.conan2 2>/dev/null || true
    sudo chmod -R 755 /root/.conan2 2>/dev/null || true
fi

# Detect all potential Conan storage locations across environments
SEARCH_DIRS=()
[ -n "$CONAN_HOME" ] && [ -d "$CONAN_HOME/p" ] && SEARCH_DIRS+=("$CONAN_HOME/p")
[ -d "/home/devcontainer/.conan2/p" ] && SEARCH_DIRS+=("/home/devcontainer/.conan2/p")
[ -d "$HOME/.conan2/p" ] && SEARCH_DIRS+=("$HOME/.conan2/p")
[ -d "/root/.conan2/p" ] && SEARCH_DIRS+=("/root/.conan2/p")

# Source Conan runtime environment if available
if [ -f "${REPO_ROOT}/build/Release/generators/conanrunenv-release-x86_64.sh" ]; then
    source "${REPO_ROOT}/build/Release/generators/conanrunenv-release-x86_64.sh" 2>/dev/null || true
fi
if [ -f "${REPO_ROOT}/build/Release/generators/conanrun.sh" ]; then
    source "${REPO_ROOT}/build/Release/generators/conanrun.sh" 2>/dev/null || true
fi

# Add all Conan package and build library directories to LD_LIBRARY_PATH
CONAN_LIBS=$(find "${SEARCH_DIRS[@]}" -name lib -type d 2>/dev/null | tr '\n' ':')
CONAN_SO_DIRS=$(find "${SEARCH_DIRS[@]}" -name '*.so' -exec dirname {} \; 2>/dev/null | sort -u | tr '\n' ':')
BUILD_LIBS=$(find "${REPO_ROOT}/build" -name '*.so' -exec dirname {} \; 2>/dev/null | sort -u | tr '\n' ':')
export LD_LIBRARY_PATH="/omnetpp/lib:${CONAN_LIBS}:${CONAN_SO_DIRS}:${BUILD_LIBS}:${REPO_ROOT}/build:${LD_LIBRARY_PATH}"

# Preload system libraries required by space_veins (PROJ)
if [ -f /usr/lib/x86_64-linux-gnu/libproj.so ]; then
    export LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libproj.so:${LD_PRELOAD}"
fi

# Prepare proper NED symlink hierarchies for Veins and subprojects
for VEINS_DIR in $(find "${SEARCH_DIRS[@]}" -type d -path '*/lib/veins/src' 2>/dev/null); do
    mkdir -p "$VEINS_DIR/org/car2x/veins/subprojects" 2>/dev/null || true
    ln -sfn ../../veins "$VEINS_DIR/org/car2x/veins" 2>/dev/null || true
    VEINS_ROOT=$(dirname "$VEINS_DIR")
    if [ -d "$VEINS_ROOT/subprojects/veins_inet/src/veins_inet" ]; then
        ln -sfn "$VEINS_ROOT/subprojects/veins_inet/src/veins_inet" "$VEINS_DIR/org/car2x/veins/subprojects/veins_inet" 2>/dev/null || true
    fi
done

# Prepare clean NED root for Simu5G
mkdir -p /tmp/ned_roots 2>/dev/null || true
SIMU5G_SRC=$(find "${SEARCH_DIRS[@]}" -type d -path '*/simu5*/b/src' 2>/dev/null | head -n 1)
if [ -n "$SIMU5G_SRC" ]; then
    ln -sfn "$SIMU5G_SRC" /tmp/ned_roots/simu5g 2>/dev/null || true
fi

# Find precise NED root paths
INET_NED=$(find "${SEARCH_DIRS[@]}" -type d -path '*/lib/inet/src' 2>/dev/null | head -n 1)
VEINS_NED=$(find "${SEARCH_DIRS[@]}" -type d -path '*/lib/veins/src' 2>/dev/null | head -n 1)
SPACE_NED=$(find "${SEARCH_DIRS[@]}" -type d -path '*/space*/s/src' 2>/dev/null | head -n 1)

NED_PATH="${REPO_ROOT}/src:${REPO_ROOT}/scenarios:/tmp/ned_roots:${INET_NED}:${VEINS_NED}:${SPACE_NED}"

# Auto-locate core OMNeT++ shared libraries from Conan packages & build
INET_LIB=$(find "${SEARCH_DIRS[@]}" -name 'libINET.so' 2>/dev/null | head -n 1)
VEINS_LIB=$(find "${SEARCH_DIRS[@]}" -name 'libveins.so' 2>/dev/null | head -n 1)
SPACE_LIB=$(find "${SEARCH_DIRS[@]}" -name 'libspace_veins.so' 2>/dev/null | head -n 1)
SIMU5G_LIB=$(find "${SEARCH_DIRS[@]}" -name 'libsimu5g.so' 2>/dev/null | head -n 1)
CORE_LIB="${REPO_ROOT}/build/libartery_core.so"
TRACI_LIB=$(find "${REPO_ROOT}/build" -name 'libtraci.so' 2>/dev/null | head -n 1)
ENVMOD_LIB=$(find "${REPO_ROOT}/build" -name 'libartery_envmod.so' 2>/dev/null | head -n 1)

LIBS_ARGS=""
[ -n "$INET_LIB" ] && LIBS_ARGS="$LIBS_ARGS -l $INET_LIB"
[ -n "$VEINS_LIB" ] && LIBS_ARGS="$LIBS_ARGS -l $VEINS_LIB"
[ -n "$SPACE_LIB" ] && LIBS_ARGS="$LIBS_ARGS -l $SPACE_LIB"
[ -n "$SIMU5G_LIB" ] && LIBS_ARGS="$LIBS_ARGS -l $SIMU5G_LIB"
[ -n "$TRACI_LIB" ] && LIBS_ARGS="$LIBS_ARGS -l $TRACI_LIB"
[ -n "$ENVMOD_LIB" ] && LIBS_ARGS="$LIBS_ARGS -l $ENVMOD_LIB"
[ -f "$CORE_LIB" ] && LIBS_ARGS="$LIBS_ARGS -l $CORE_LIB"

exec opp_run -n "${NED_PATH}" $LIBS_ARGS "$@"
