cmake_minimum_required(VERSION 3.20)

cmake_policy(VERSION 3.20...3.31)

project(NexaSim VERSION 1.0.0 LANGUAGES CXX C)

enable_testing()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

list(APPEND CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake)

###################
# NexaSim Options #
###################

# Core domain integrations
option(WITH_INET "Build NexaSim with INET framework integration" ON)
option(WITH_VEINS "Build NexaSim with Veins framework integration" ON)
option(WITH_NTN "Build NexaSim with NTN/space_veins integration" ON)
option(WITH_SIMU5G "Build NexaSim with Simu5G/NR integration" ON)
option(WITH_ENVMOD "Build NexaSim with environment model feature" ON)

# Scenarios & Tools
option(WITH_SCENARIOS "Build NexaSim with scenarios" ON)
option(VSCODE_LAUNCH_INTEGRATION "Generate VS Code configuration for debugging (requires debug build)" OFF)

##############################
# Artery build configuration #
##############################

# use "RelWithDebInfo" as default build type
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE "RelWithDebInfo" CACHE STRING "CMake build type" FORCE)
    set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

# running simulations with opp_run requires shared libraries
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(BUILD_SHARED_LIBS ON CACHE INTERNAL "Cached for propagation to sub-projects with older CMake versions")
add_compile_definitions(PI=PI)

###############################
# Required packages & scripts #
###############################

list(APPEND CMAKE_PREFIX_PATH "${CMAKE_BINARY_DIR}/Release/generators" "${CMAKE_BINARY_DIR}/generators" "${CMAKE_CURRENT_BINARY_DIR}/generators")
list(APPEND CMAKE_MODULE_PATH "${CMAKE_BINARY_DIR}/Release/generators" "${CMAKE_BINARY_DIR}/generators" "${CMAKE_CURRENT_BINARY_DIR}/generators")

set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)
set(Boost_NO_SYSTEM_PATHS ON)

find_package(OmnetPP 5.5.1 MODULE REQUIRED)
find_package(Boost REQUIRED CONFIG)
if(NOT TARGET boost::boost)
    add_library(boost::boost INTERFACE IMPORTED)
    if(TARGET Boost::headers)
        target_link_libraries(boost::boost INTERFACE Boost::headers)
    endif()
endif()

include(AddOppRun)
include(AddOppTarget)
include(AddVSCode)
include(ArteryCodegen)
include(AddArterySubdirectory)
include(GNUInstallDirs)

# Packages below are needed by various
# optional components. They should be used
# with add_artery_subdirectory() to trigger
# checks on them only if variables (WITH*)
# are set.

find_package(Protobuf QUIET)
find_package(SEA_V2X CONFIG QUIET)

if(SEA_V2X_FOUND)
    mark_as_advanced(SEA_V2X_DIR)
endif()

find_package(Vanetza REQUIRED)
find_package(INET REQUIRED)
find_package(space_veins REQUIRED)
find_package(Simu5G REQUIRED)

##########################
# Primary Artery targets #
##########################

add_library(artery INTERFACE)
add_library(NexaSim::NexaSim ALIAS artery)
add_library(Artery::Artery ALIAS artery)

add_library(core SHARED)
add_library(Artery::Core ALIAS core)
add_library(NexaSim::Core ALIAS core)

macro(add_artery_feature name)
    add_library(${name} SHARED ${ARGN})
    add_library(Artery::${name} ALIAS ${name})
    get_target_property(ned_folder ${name} SOURCE_DIR)
    set_target_properties(${name} PROPERTIES
        OUTPUT_NAME artery_${name}
        OMNETPP_LIBRARY ON
        NED_FOLDERS ${ned_folder})
    target_link_libraries(${name} PRIVATE core)
    target_include_directories(${name} PUBLIC ${PROJECT_SOURCE_DIR}/src ${PROJECT_BINARY_DIR}/opp_messages)
    target_link_libraries(artery INTERFACE Artery::${name})
    install(TARGETS ${name} LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR})
endmacro()

##########
# Artery #
##########

add_subdirectory(src/artery)
add_subdirectory(src/traci)

# scenarios directory is part of repository but omitted for Docker build context
if(WITH_SCENARIOS)
    add_subdirectory(scenarios)
endif()

get_property(is_multi_config GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)

if(is_multi_config)
    foreach(config IN LISTS CMAKE_CONFIGURATION_TYPES)
        string(TOLOWER "${config}" config_lower)
        generate_run_config(TARGET artery CONFIG ${config} FILE "${PROJECT_BINARY_DIR}/run-artery.${config}.ini")
        generate_run_config(TARGET artery CONFIG ${config} FILE "${PROJECT_BINARY_DIR}/run-artery.${config}.ini.install" INSTALL)
    endforeach()
else()
    generate_run_config(TARGET artery CONFIG ${CMAKE_BUILD_TYPE} FILE "${PROJECT_BINARY_DIR}/run-artery.ini")
    generate_run_config(TARGET artery CONFIG ${CMAKE_BUILD_TYPE} FILE "${PROJECT_BINARY_DIR}/run-artery.ini.install" INSTALL)
endif()

if(VSCODE_LAUNCH_INTEGRATION)
    if(is_multi_config AND "Debug" IN_LIST CMAKE_CONFIGURATION_TYPES)
        message(STATUS "VS Code integration is enabled, but Debug is not included in build types")
    elseif(NOT "${CMAKE_BUILD_TYPE}" STREQUAL "Debug")
        message(STATUS "VS Code integration is enabled, but build type is not Debug")
    else()
        generate_vscode(TARGET artery FILE ${PROJECT_SOURCE_DIR}/.vscode/launch.json)
    endif()
endif()
