import conan
import os
from conan import ConanFile
from conan.tools.files import get, copy, replace_in_file
from conan.tools.layout import basic_layout

class SpaceVeinsConan(ConanFile):
    name = "space_veins"
    version = "0.3"
    settings = "os", "compiler", "build_type", "arch"

    # space_veins dipende da inet in molti casi se viene usato in ecosistema OMNeT++
    def requirements(self):
        self.requires("inet/4.2.2")

    def source(self):
        self.output.info("Downloading space_veins 0.3 source...")
        get(self, "https://github.com/veins/space_veins/archive/refs/tags/space_Veins-0.3.tar.gz", strip_root=True)

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

        # Build veins first
        self.output.info("Building veins...")
        veins_src = os.path.join(self.source_folder, "lib", "veins", "src")
        veins_out = os.path.join(self.source_folder, "lib", "veins", "out", f"gcc-{opp_mode}", "src")
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && opp_makemake -f --deep --no-deep-includes --make-so -I. -o veins -O out -p VEINS", cwd=veins_src)
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && make -j{os.cpu_count()} MODE={opp_mode}", cwd=veins_src)

        # Build veins_inet
        self.output.info("Building veins_inet...")
        veins_inet_src = os.path.join(self.source_folder, "lib", "veins", "subprojects", "veins_inet", "src")
        veins_inet_out = os.path.join(self.source_folder, "lib", "veins", "subprojects", "veins_inet", "out", f"gcc-{opp_mode}", "src")
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && opp_makemake -f --deep --no-deep-includes --make-so -I. -o veins_inet -O out -p VEINS_INET -I{inet_inc} -L{inet_lib} -lINET -I{veins_src} -L{veins_out} -lveins", cwd=veins_inet_src)
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && make -j{os.cpu_count()} MODE={opp_mode}", cwd=veins_inet_src)

        # Build space_veins
        self.output.info("Configuring space_veins project...")
        space_veins_src = os.path.join(self.source_folder, "src")
        makemake_cmd = (
            f"opp_makemake -f --deep --no-deep-includes --make-so -I. -o space_veins -O out -p SPACE_VEINS "
            f"-I{inet_inc} -L{inet_lib} -lINET "
            f"-I{veins_src} -L{veins_out} -lveins "
            f"-I{veins_inet_src} -L{veins_inet_out} -lveins_inet"
        )
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && {makemake_cmd}", cwd=space_veins_src)
        self.run(f"export PATH=/omnetpp/bin:{bin_dir}:$PATH && make -j{os.cpu_count()} MODE={opp_mode}", cwd=space_veins_src)

    def package(self):
        # Copia headers space_veins
        copy(self, "*.h", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "include"))
        # Copia headers veins
        copy(self, "*.h", src=os.path.join(self.source_folder, "lib", "veins", "src"), dst=os.path.join(self.package_folder, "include"))
        # Copia headers veins_inet
        copy(self, "*.h", src=os.path.join(self.source_folder, "lib", "veins", "subprojects", "veins_inet", "src"), dst=os.path.join(self.package_folder, "include"))
        
        # Copia i binari space_veins (.so, .a, .dll) dipendendo dal SO
        copy(self, "*.so", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.a", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "lib"), keep_path=False)

        # Copia binari veins e veins_inet
        copy(self, "*.so", src=os.path.join(self.source_folder, "lib", "veins"), dst=os.path.join(self.package_folder, "lib"), keep_path=False)
        copy(self, "*.a", src=os.path.join(self.source_folder, "lib", "veins"), dst=os.path.join(self.package_folder, "lib"), keep_path=False)

        # Copia i file NED (necessari a OMNeT++)
        copy(self, "*.ned", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "share/ned"), keep_path=False)
        copy(self, "*.ned", src=os.path.join(self.source_folder, "lib", "veins", "src"), dst=os.path.join(self.package_folder, "share/ned"), keep_path=False)
        copy(self, "*.ned", src=os.path.join(self.source_folder, "lib", "veins", "subprojects", "veins_inet", "src"), dst=os.path.join(self.package_folder, "share/ned"), keep_path=False)

        # Copia i messaggi (facoltativo se ci sono anche le class generate)
        copy(self, "*.msg", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "share/msg"), keep_path=False)

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "space_veins")
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_target_name", "space_veins::space_veins")
        
        self.cpp_info.libs = ["space_veins", "veins_inet", "veins"]
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
