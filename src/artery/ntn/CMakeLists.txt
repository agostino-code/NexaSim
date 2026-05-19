# src/artery/ntn/CMakeLists.txt
set_target_properties(core PROPERTIES
    NED_FOLDERS ${CMAKE_CURRENT_SOURCE_DIR}
)

target_sources(core PRIVATE
    LEO_Satellite.cc
    GroundStation.cc
)
