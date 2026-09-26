target_sources(core PRIVATE
    HybridInterfaceManager.cc
    MecOffloadingClient.cc
    MecEdgeServer.cc
)

add_opp_message(mec-task-packet MESSAGE MecTaskPacket.msg)

target_link_libraries(core PRIVATE mec-task-packet)

target_include_directories(core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)
