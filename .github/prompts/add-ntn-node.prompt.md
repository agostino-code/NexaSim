---
name: "add-ntn-node"
description: "Scaffold a space_veins Non-Terrestrial Network (NTN) node component (C++ source, NED file, OMNeT++ config)."
argument-hint: "Provide the name of the new NTN node (e.g. LEO_Satellite, GroundStation)."
agent: "agent"
tools: [read, edit, search]
---

You are an expert in OMNeT++, Veins, and the `space_veins` framework for the NexaSphere project.

Your task is to scaffold a new Non-Terrestrial Network (NTN) node.

**Inputs:**
The user will provide the desired name of the NTN node as an argument (e.g., `LEO_Satellite` or `GroundStation`).

**Requirements:**
1. **C++ Header and Source**: Generate a basic OMNeT++ simple module class inheriting from an appropriate Veins/INET base class (or `space_veins` specific base if inferred).
2. **NED File**: Create a corresponding `.ned` file that defines the network module, its gates, and parameters, ensuring it belongs to the correct package (e.g., `artery.veins` or `artery.inet`).
3. **CMake Integration**: Provide the exact `edit` instructions to add the new `.cc` file to the appropriate `CMakeLists.txt`.
4. **Configuration**: Show how to include this node in `omnetpp.ini`.

**Guidelines:**
- Ensure the code adheres to modern C++ conventions and the OMNeT++ API.
- Do not run build commands automatically; just create the files.
- Put the generated files in the standard source directories (`src/artery/`).