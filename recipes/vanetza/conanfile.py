from conan import ConanFile
from conan.tools.cmake import CMake, cmake_layout, CMakeToolchain, CMakeDeps
from conan.tools.files import copy
import os

class VanetzaConan(ConanFile):
    name = "vanetza"
    version = "26.02"
    url = "https://github.com/riebl/vanetza"
    license = "LGPL-3.0-or-later"
    settings = "os", "compiler", "build_type", "arch"
    
    options = {
        "fPIC": [True, False],
        "shared": [True, False],
        "testing": [True, False],
        "with_openssl": [True, False],
    }
    default_options = {
        "fPIC": True,
        "shared": True,
        "testing": False,
        "with_openssl": False,
    }

    def source(self):
        from conan.tools.files import get
        get(self, f"{self.url}/archive/refs/tags/v{self.version}.tar.gz", strip_root=True)

    def config_options(self):

        if self.settings.os == "Windows":
            del self.options.fPIC

    def requirements(self):
        self.requires("boost/1.86.0")
        self.requires("cryptopp/8.9.0")
        self.requires("geographiclib/2.3")

    def layout(self):
        cmake_layout(self)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["VANETZA_WITH_OPENSSL"] = self.options.with_openssl
        tc.variables["BUILD_TESTS"] = self.options.testing
        tc.generate()
        
        deps = CMakeDeps(self)
        deps.set_property("cryptopp", "cmake_file_name", "CryptoPP")
        deps.set_property("geographiclib", "cmake_file_name", "GeographicLib")
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        copy(self, "*.hpp", src=self.source_folder, dst=os.path.join(self.package_folder, "include"))
        copy(self, "*.h", src=self.source_folder, dst=os.path.join(self.package_folder, "include"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Vanetza")
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_target_name", "Vanetza::vanetza")
        self.cpp_info.set_property("cmake_target_alias", "vanetza::vanetza")
        self.cpp_info.includedirs = [
            "include",
            "include/vanetza/asn1/its",
            "include/vanetza/asn1/its_r2",
            "include/vanetza/asn1/security",
            "include/vanetza/asn1/security_r2",
            "include/vanetza/asn1/support",
        ]
        self.cpp_info.libdirs = ["lib"]
        
        libs = ['access', 'asn1', 'asn1_its', 'asn1_its_r2', 'asn1_security', 'asn1_security_r2', 'asn1_support',
                'btp', 'common', 'dcc', 'facilities', 'geonet', 'gnss', 'net', 'security']
        self.cpp_info.libs = ['vanetza_' + lib for lib in libs]
