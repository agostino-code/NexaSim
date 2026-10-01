# src/artery/ntn/CMakeLists.txt
add_artery_feature(ntn
    LEO_SatelliteManager.cc
    GroundStationManager.cc
    ConstellationManager.cc
    ISLNic.cc
    UserTerminal.cc
    UnifiedMobilityManager.cc
    NTNChannelModel.cc
    NTNPathLoss.cc
)

target_link_libraries(ntn PUBLIC space_veins::space_veins INET::INET)

# NTN components often interact with 5G-NR via Unified Mobility Management
if(TARGET nr)
    target_link_libraries(ntn PUBLIC nr)
endif()
