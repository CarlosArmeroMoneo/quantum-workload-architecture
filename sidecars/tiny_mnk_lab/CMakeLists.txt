cmake_minimum_required(VERSION 3.24)

project(tiny_mnk_lab LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

add_executable(tiny_mnk_bench src/tiny_mnk_bench.cu)
target_compile_features(tiny_mnk_bench PRIVATE cxx_std_17)
set_target_properties(
    tiny_mnk_bench
    PROPERTIES
        CUDA_SEPARABLE_COMPILATION ON
        CUDA_ARCHITECTURES "75"
)
