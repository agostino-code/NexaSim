import conan
import os
from conan import ConanFile
from conan.tools.files import get, copy, replace_in_file
from conan.tools.layout import basic_layout


class Simu5GConan(ConanFile):
    name = "simu5g"
    version = "1.1.0"
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        self.requires("inet/4.2.2")

    def source(self):
        self.output.info("Downloading Simu5G 1.1.0 source...")
        get(self, "https://github.com/Unipisa/Simu5G/archive/refs/tags/v1.1.0.tar.gz", strip_root=True)

    def layout(self):
        basic_layout(self)

    def build(self):
        # Symlink per 'python' -> 'python3' come fallback temporaneo per opp_makemake
        bin_dir = os.path.join(self.build_folder, "temp_bin")
        os.makedirs(bin_dir, exist_ok=True)
        py_symlink = os.path.join(bin_dir, "python")
        if not os.path.exists(py_symlink):
            os.symlink("/usr/bin/python3", py_symlink)

        mode = "debug" if self.settings.build_type == "Debug" else "release"
        opp_mode = "debug" if self.settings.build_type == "Debug" else "release"

        inet_info = self.dependencies["inet"].cpp_info
        inet_inc = inet_info.includedirs[0]
        inet_lib = inet_info.libdirs[0]

        # Patch API differences for INET 4.2.2 compatibility
        simu5g_src = os.path.join(self.source_folder, "src")
        lte_common_h = os.path.join(simu5g_src, "common", "LteCommon.h")
        if os.path.exists(lte_common_h):
            replace_in_file(self, lte_common_h, "tags.getTagForUpdate(i)", "tags.getTag(i)", strict=False)

        for root, _, files in os.walk(simu5g_src):
            for file in files:
                if file.endswith(".cc") or file.endswith(".h"):
                    filepath = os.path.join(root, file)
                    replace_in_file(self, filepath, "findModuleByPath", "getModuleByPath", strict=False)
                    replace_in_file(self, filepath, "NetworkInterface *", "InterfaceEntry *", strict=False)
                    replace_in_file(self, filepath, "NetworkInterface*", "InterfaceEntry*", strict=False)

        # Build Simu5G
        self.output.info("Configuring Simu5G project...")
        makemake_cmd = (
            f"opp_makemake -f --deep --no-deep-includes --make-so -I. -o simu5g -O out -p SIMU5G "
            f"-I{inet_inc} -L{inet_lib} -lINET"
        )
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && {makemake_cmd}", cwd=simu5g_src)
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && make -j{os.cpu_count()} MODE={opp_mode}", cwd=simu5g_src)

    def package(self):
        # Copia headers
        copy(self, "*.h", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "include"))
        
        # Copia i binari (.so, .a, .dll) dipendendo dal SO
        copy(self, "*.so", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.a", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "lib"), keep_path=False)

        # Copia i file NED (necessari a OMNeT++)
        copy(self, "*.ned", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "share/ned"), keep_path=False)
        copy(self, "*.msg", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "share/msg"), keep_path=False)

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Simu5G")
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_target_name", "Simu5G::simu5g")
        self.cpp_info.set_property("cmake_target_alias", "simu5g::simu5g")

        self.cpp_info.libs = ["simu5g"]
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]