import conan

from typing import Callable, Mapping, Any
from conan.tools.cmake import cmake_layout


class NexaSim(conan.ConanFile):
    name = 'nexasim'
    version = '1.0.0'
    description = 'NexaSim: 3D Unified Terrestrial and Non-Terrestrial Network Simulator (Horizon Europe NexaSphere)'
    generators = ['CMakeToolchain', 'CMakeDeps']
    settings = ['os', 'compiler', 'build_type', 'arch']
    default_options = {
        'vanetza/*:shared': True,
    }

    # dynamically set conanfile attributes
    conan_data: Mapping[str, Any]
    requires: Callable[[str], None]

    def requirements(self):
        for req, version in self.conan_data['requirements'].items():
            self.requires(f'{req}/{version}')

    def layout(self):
        cmake_layout(self)
