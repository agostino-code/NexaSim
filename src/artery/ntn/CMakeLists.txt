# src/artery/ntn/CMakeLists.txt
set_target_properties(core PROPERTIES
    NED_FOLDERS ${CMAKE_CURRENT_SOURCE_DIR}
)

target_sources(core PRIVATE
    LEO_SatelliteManager.cc
    GroundStationManager.cc
    ConstellationManager.cc
    ISLNic.cc
    UserTerminal.cc
    UnifiedMobilityManager.cc
    NTNChannelModel.cc
    NTNPathLoss.cc
)

target_link_libraries(core PUBLIC space_veins::space_veins INET::INET)
