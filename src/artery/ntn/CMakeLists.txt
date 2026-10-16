# src/artery/ntn/CMakeLists.txt
#
# NTN (Non-Terrestrial Network) module: LEO satellites, ground stations,
# inter-satellite links, channel/path-loss models, and unified mobility.
#
# Dependency-modularity (per docs/proposed-cmake-modularity.md):
#   - ntn_core   : dependency-free abstract interface layer (pure C++17);
#                  carries no INET / Simu5G / space_veins includes.
#   - ntn        : concrete OMNeT++ feature linking external dependencies
#                  through Conan-provided imported targets
#                  (space_veins::space_veins, INET::INET).
#                  Framework-specific adapters (ntn::InetMobilityProvider)
#                  live here, never in ntn_core.

# --- Abstract interface layer (no INET / Simu5G / space_veins coupling) ---
add_library(ntn_core INTERFACE
    interfaces/MobilityTypes.h
    interfaces/INetworkMobilityProvider.h
    interfaces/IRadioLinkMetricsProvider.h
)
target_include_directories(ntn_core INTERFACE
    $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/src>
)
add_library(Artery::NtnCore ALIAS ntn_core)
add_library(NexaSim::NtnCore ALIAS ntn_core)

# The Artery core (hosting hybrid::HybridInterfaceManager) consumes the
# abstract NTN interfaces; concrete adapters remain in this feature.
if(TARGET core)
    target_link_libraries(core PUBLIC ntn_core)
endif()

# --- Concrete NTN feature ---
add_artery_feature(ntn
    LEO_SatelliteManager.cc
    GroundStationManager.cc
    ConstellationManager.cc
    ISLNic.cc
    UserTerminal.cc
    UnifiedMobilityManager.cc
    NTNChannelModel.cc
    NTNPathLoss.cc
    providers/InetMobilityProvider.cc
)

# Link abstract interfaces first so consumers see them through the ntn target,
# then external dependencies through Conan-imported targets.
target_link_libraries(ntn PUBLIC
    ntn_core
    space_veins::space_veins
    INET::INET
)

# NTN components often interact with 5G-NR via Unified Mobility Management
if(TARGET nr)
    target_link_libraries(ntn PUBLIC nr)
endif()
