# Proposed CMake Modularization for NexaSim

## Current Issue
Some components in `src/artery` (like `nr` and `ntn`) directly couple external dependencies such as INET, Simu5G, and space_veins. This tight coupling decreases modularity and makes scaling components or replacing individual modules challenging.

## Proposed Solution
Introduce abstracts to create intermediate interfaces that cleanly separate dependency management from core modules. The new structure will enhance code reuse, simplify dependency updates, and improve clarity.

### Steps to Modularize
1. **Introduce Abstract Interface Libraries**:
   - Create `ntn_core` and `nr_core` as intermediate modules.
   - Example:
     ```cmake
     # src/artery/ntn/CMakeLists.txt
     add_library(ntn_core SHARED
       NTNBase.cc
       NTNUtils.cc
     )

     target_include_directories(ntn_core
       PUBLIC
         ${PROJECT_SOURCE_DIR}/src/libcore
     )

     target_link_libraries(ntn_core
       PUBLIC
         space_veins::space_veins
         INET::INET
     )
     ```

2. **Refactor Dependent Components**:
    Modules like `LEOSatelliteManager` or `GNBHandler` will link to the abstracts (`ntn_core`/`nr_core`) instead of directly linking external dependencies.

3. **Use Conan Targets for Flexibility**:
    Rewrite `find_package` usage to interface with Conan-generated targets cleanly, ensuring reproducible builds and declarative version locks.
    ```cmake
    find_package(Space_Veins REQUIRED)
    find_package(Simu5G CONFIG)

    target_link_libraries(core_common_sim
        PUBLIC
          Simu5G::sim5
          Space_Veins::core_modules)
...

 Next split examples-layout runners+=