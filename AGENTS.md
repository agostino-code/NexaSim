# NexaSim Development Agent Instructions

## Project Context: NexaSphere (NexaSim Simulator)
This repository contains **NexaSim**, a 3D Unified Terrestrial & Non-Terrestrial Network Simulator developed for **NexaSphere**, a Horizon Europe research and innovation project.
- **Goal**: Designing and validating a unified three-dimensional (3D) communication network.
- **Domains**: Integrates terrestrial (TN: V2X, 5G-NR), non-terrestrial (NTN: LEO constellations, ISL, User Terminals), and aerial systems.
- **Architecture**: Zero-submodule architecture using Conan 2 for all external dependencies (INET 4.2.2, Simu5G 1.1.0, space_veins 0.3, Vanetza 26.02).

## Development Environment
- **Docker Only**: All commands (build, run, test, Conan operations) MUST be executed inside the `artery-dev` Docker container. Do not run host-level commands unless explicitly requested.
- **Workflow Wrapper**: Prefix terminal commands or ensure you are running them in an interactive shell attached to `artery-dev`.

## Architecture & Conventions

### Dependency Management (Conan)
- **Do not use `extern/`**. We are systematically replacing internal modules located in `extern/` (e.g., INET, Veins, Vanetza) with Conan packages.
- All new or updated dependencies should be defined in `conanfile.py` and `conandata.yml`. 
- Leverage existing Conan Center packages where possible to minimize internally maintained codebase size.

### Build System (CMake)
- **Avoid add_subdirectory** for external libraries.
- Instead, use `find_package(...)` in `CMakeLists.txt` and rely on Conan's `CMakeDeps` and `CMakeToolchain` generators.
- Always link against imported targets provided by Conan (e.g., `target_link_libraries(target PUBLIC Package::Package)`).
- Ensure reproducible builds by relying entirely on the locked versions in Conan instead of Git submodules.

### space_veins Integration
- Any satellite or non-terrestrial network (NTN) components should reference or integrate concepts from [`veins/space_veins`](https://github.com/veins/space_veins).

## AI Agent Instructions
When you interact with the codebase:
1. **Container Execution:** Explicitly state and use Docker commands to interact with the build system.
2. **Conan over Git:** If a library is missing, reach for `conanfile.py` rather than proposing a `git submodule add`.
3. **Refactoring CMake:** When reviewing or modifying `CMakeLists.txt`, ensure legacy references to `extern/` are stripped out, and replace them with standard `find_package` calls aligned with Conan.
