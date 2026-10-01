# src/artery/nr/CMakeLists.txt
add_artery_feature(nr
    NRManager.cc
)

target_link_libraries(nr PUBLIC Simu5G::simu5g INET::INET)
