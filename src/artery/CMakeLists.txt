# Artery core modules
add_subdirectory(nic)
add_subdirectory(traci)
add_subdirectory(utility)
add_subdirectory(networking)
add_subdirectory(application)
add_subdirectory(hybrid)

target_sources(core PRIVATE
    StaticNodeManager.cc
)

target_link_libraries(artery INTERFACE core)

set_target_properties(core PROPERTIES
    OUTPUT_NAME artery_core
    OMNETPP_LIBRARY ON
    NED_FOLDERS ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(core PUBLIC
    ${PROJECT_SOURCE_DIR}/src
    ${Boost_INCLUDE_DIRS}
    $<TARGET_PROPERTY:Vanetza::vanetza,INTERFACE_INCLUDE_DIRECTORIES>
    $<TARGET_PROPERTY:INET::INET,INTERFACE_INCLUDE_DIRECTORIES>
)

target_link_libraries(core PUBLIC
    ${Boost_LIBRARIES}
    OmnetPP::envir
    traci
    Vanetza::vanetza
    INET::INET
)

add_artery_subdirectory(veins SWITCH WITH_VEINS)
add_artery_subdirectory(inet SWITCH WITH_INET)
add_artery_subdirectory(ntn REQUIRES space_veins::space_veins SWITCH WITH_NTN)
add_artery_subdirectory(nr REQUIRES Simu5G::simu5g SWITCH WITH_SIMU5G)

add_artery_subdirectory(envmod REQUIRES INET::INET SWITCH WITH_ENVMOD)

if(WITH_ENVMOD)
    set_property(SOURCE application/VehicleMiddleware.cc APPEND PROPERTY COMPILE_DEFINITIONS "WITH_ENVMOD")
endif()

install(TARGETS core LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/ DESTINATION share/ned/artery FILES_MATCHING PATTERN "*.ned")

set_property(TARGET core APPEND PROPERTY INSTALL_NED_FOLDERS ${CMAKE_INSTALL_DATADIR}/ned/artery)
