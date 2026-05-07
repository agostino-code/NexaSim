---
name: manage-conan-dependencies
description: 'Use when: adding a new library, updating an existing C++ dependency, transitioning a module from extern/, or fixing CMake configuration related to packages.'
---

# Manage Conan Dependencies

This skill provides a standard workflow for managing C++ dependencies using Conan and integrating them into Artery's CMake build system, tailored for the NexaSphere project structure.

## Workflow

1. **Verify Package on Conan Center**
   - Search for the required package on Conan Center (e.g., via `conan search <pkg>* -r conancenter` inside the `artery-dev` Docker container or via web).
   - Determine the correct version to use.

2. **Update Conan Configuration**
   - **`conandata.yml`**: Add the dependency and version under the `requirements:` section.
   - **`conanfile.py`**: No direct changes needed unless specific Conan options are required, as `conanfile.py` dynamically reads from `conandata.yml`.

3. **Refactor `CMakeLists.txt`**
   - Locate the target where the dependency is needed.
   - Remove any legacy `add_subdirectory(extern/<module>)` or custom find modules.
   - Add `find_package(<PackageName> REQUIRED)` matching the Conan generated CMakeDeps name.
   - Update `target_link_libraries(<target> PUBLIC <PackageName>::<PackageName>)`.

4. **Verify via Docker**
   - Instruct the user (or use `run_in_terminal`) to execute the build inside the `artery-dev` Docker container:
     ```bash
     docker exec -it artery-dev bash -c "conan install . --build=missing && cmake --preset Release && cmake --build build/Release"
     ```
   - Ensure the build succeeds and links properly without falling back to internal `extern/` dependencies.

## Checklists & Criteria
- [ ] Dependency explicitly defined in `conandata.yml`.
- [ ] No lingering `extern/` dependencies matching the newly added package.
- [ ] Correct Conan CMake target names used in `target_link_libraries`.
- [ ] Build succeeds strictly within the `artery-dev` Docker container.