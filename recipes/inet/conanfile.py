import conan
import os
from conan import ConanFile
from conan.tools.files import get, copy, replace_in_file
from conan.tools.layout import basic_layout

class InetConan(ConanFile):
    name = "inet"
    version = "4.2.2"
    settings = "os", "compiler", "build_type", "arch"
    
    def source(self):
        # Scarica i sorgenti di INET framework dal tag ufficiale
        self.output.info("Downloading INET 4.2.2 source...")
        get(self, "https://github.com/inet-framework/inet/archive/refs/tags/v4.2.2.tar.gz", strip_root=True)

    def layout(self):
        basic_layout(self)

    def build(self):
        # Crea un symlink temporaneo così che i tool OMNeT++ / INET trovino 'python'
        bin_dir = os.path.join(self.build_folder, "temp_bin")
        os.makedirs(bin_dir, exist_ok=True)
        py_symlink = os.path.join(bin_dir, "python")
        if not os.path.exists(py_symlink):
            os.symlink("/usr/bin/python3", py_symlink)

        # In Conan 2, self.run() accetta env come stringa, per "PATH" preferiamo iniettarlo localmente al comando
        self.output.info("Generating makefiles...")
        self.run(f"export PATH={bin_dir}:$PATH && opp_featuretool disable wirelesstutorial configuratortutorial", cwd=self.source_folder)
        self.run(f"export PATH={bin_dir}:$PATH && make makefiles", cwd=self.source_folder)
        
        # Compila in base a CMAKE_BUILD_TYPE mappandolo sui MODE di OMNeT++ 
        mode = "debug" if self.settings.build_type == "Debug" else "release"
        self.output.info(f"Compiling INET in {mode} mode...")
        self.run(f"export PATH={bin_dir}:$PATH && make -j{os.cpu_count()} MODE={mode}", cwd=self.source_folder)

    def package(self):
        # Copia headers
        copy(self, "*.h", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "include"))
        # Copia i binari (.so, .a, .dll) dipendendo dal SO
        copy(self, "*.so", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "lib"))
        copy(self, "*.a", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "lib"))
        # Copia i file NED (necessari a OMNeT++) e .msg
        copy(self, "*.ned", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "share/ned"))
        copy(self, "*.msg", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "include"))
        copy(self, "*.ned", src=os.path.join(self.source_folder, "src"), dst=os.path.join(self.package_folder, "include"))
        # Copia the _scripts folder so other configure scripts can find get_version
        copy(self, "*", src=os.path.join(self.source_folder, "_scripts"), dst=os.path.join(self.package_folder, "_scripts"))
        # Provide a symlink to include named src, because space_veins's configure looks for src/inet/...
        os.symlink("include", os.path.join(self.package_folder, "src"))

    def package_info(self):
        self.cpp_info.libs = ["INET"]
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
