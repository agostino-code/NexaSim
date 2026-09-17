# src/artery/nr/CMakeLists.txt
set_target_properties(core PROPERTIES
    NED_FOLDERS ${CMAKE_CURRENT_SOURCE_DIR}
)

target_sources(core PRIVATE
    NRManager.cc
)

target_link_libraries(core PUBLIC Simu5G::simu5g INET::INET)
