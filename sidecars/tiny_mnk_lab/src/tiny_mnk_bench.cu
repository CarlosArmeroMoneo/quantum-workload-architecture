#include <cuda_runtime.h>
#include <cuComplex.h>

#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Config {
    int m = 32;
    int n = 256;
    int k = 75;
    int warmup = 5;
    int iters = 50;
    std::string label = "tiny_mnk_reference";
    std::string csv_out;
};

void check_cuda(cudaError_t status, const char* message) {
    if (status != cudaSuccess) {
        throw std::runtime_error(std::string(message) + ": " + cudaGetErrorString(status));
    }
}

__global__ void tiny_mnk_gemm_kernel(
    const cuDoubleComplex* a,
    const cuDoubleComplex* b,
    cuDoubleComplex* c,
    int m,
    int n,
    int k
) {
    const int row = blockIdx.y * blockDim.y + threadIdx.y;
    const int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= m || col >= n) {
        return;
    }

    cuDoubleComplex acc = make_cuDoubleComplex(0.0, 0.0);
    for (int kk = 0; kk < k; ++kk) {
        acc = cuCadd(acc, cuCmul(a[row * k + kk], b[kk * n + col]));
    }
    c[row * n + col] = acc;
}

Config parse_args(int argc, char** argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto require_value = [&](const char* flag) -> const char* {
            if (i + 1 >= argc) {
                throw std::runtime_error(std::string("missing value for ") + flag);
            }
            return argv[++i];
        };
        if (arg == "--m") {
            cfg.m = std::stoi(require_value("--m"));
        } else if (arg == "--n") {
            cfg.n = std::stoi(require_value("--n"));
        } else if (arg == "--k") {
            cfg.k = std::stoi(require_value("--k"));
        } else if (arg == "--warmup") {
            cfg.warmup = std::stoi(require_value("--warmup"));
        } else if (arg == "--iters") {
            cfg.iters = std::stoi(require_value("--iters"));
        } else if (arg == "--label") {
            cfg.label = require_value("--label");
        } else if (arg == "--csv-out") {
            cfg.csv_out = require_value("--csv-out");
        } else if (arg == "--help" || arg == "-h") {
            std::cout
                << "tiny_mnk_bench --m <int> --n <int> --k <int> --warmup <int> --iters <int> "
                << "--label <name> --csv-out <path>\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }
    if (cfg.csv_out.empty()) {
        throw std::runtime_error("--csv-out is required");
    }
    if (cfg.m <= 0 || cfg.n <= 0 || cfg.k <= 0 || cfg.warmup < 0 || cfg.iters <= 0) {
        throw std::runtime_error("m/n/k must be > 0, warmup must be >= 0, and iters must be > 0");
    }
    return cfg;
}

double gflops_for(int m, int n, int k, float latency_ms) {
    const double flops = 8.0 * static_cast<double>(m) * static_cast<double>(n) * static_cast<double>(k);
    const double latency_s = static_cast<double>(latency_ms) / 1000.0;
    return latency_s > 0.0 ? flops / latency_s / 1.0e9 : 0.0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Config cfg = parse_args(argc, argv);
        const std::size_t a_elems = static_cast<std::size_t>(cfg.m) * static_cast<std::size_t>(cfg.k);
        const std::size_t b_elems = static_cast<std::size_t>(cfg.k) * static_cast<std::size_t>(cfg.n);
        const std::size_t c_elems = static_cast<std::size_t>(cfg.m) * static_cast<std::size_t>(cfg.n);

        std::vector<cuDoubleComplex> host_a(a_elems);
        std::vector<cuDoubleComplex> host_b(b_elems);
        for (std::size_t idx = 0; idx < host_a.size(); ++idx) {
            host_a[idx] = make_cuDoubleComplex(static_cast<double>((idx % 17) + 1) / 17.0, 0.0);
        }
        for (std::size_t idx = 0; idx < host_b.size(); ++idx) {
            host_b[idx] = make_cuDoubleComplex(static_cast<double>((idx % 13) + 1) / 13.0, 0.0);
        }

        cuDoubleComplex* dev_a = nullptr;
        cuDoubleComplex* dev_b = nullptr;
        cuDoubleComplex* dev_c = nullptr;
        check_cuda(cudaMalloc(&dev_a, host_a.size() * sizeof(cuDoubleComplex)), "cudaMalloc(A)");
        check_cuda(cudaMalloc(&dev_b, host_b.size() * sizeof(cuDoubleComplex)), "cudaMalloc(B)");
        check_cuda(cudaMalloc(&dev_c, c_elems * sizeof(cuDoubleComplex)), "cudaMalloc(C)");
        check_cuda(cudaMemcpy(dev_a, host_a.data(), host_a.size() * sizeof(cuDoubleComplex), cudaMemcpyHostToDevice), "cudaMemcpy(A)");
        check_cuda(cudaMemcpy(dev_b, host_b.data(), host_b.size() * sizeof(cuDoubleComplex), cudaMemcpyHostToDevice), "cudaMemcpy(B)");

        const dim3 block(16, 16, 1);
        const dim3 grid((cfg.n + block.x - 1) / block.x, (cfg.m + block.y - 1) / block.y, 1);

        for (int iter = 0; iter < cfg.warmup; ++iter) {
            tiny_mnk_gemm_kernel<<<grid, block>>>(dev_a, dev_b, dev_c, cfg.m, cfg.n, cfg.k);
        }
        check_cuda(cudaDeviceSynchronize(), "cudaDeviceSynchronize(warmup)");

        std::ofstream out(cfg.csv_out, std::ios::out | std::ios::trunc);
        out << "label,m,n,k,iteration,latency_ms,gflops,block_x,block_y,grid_x,grid_y,status\n";

        for (int iter = 0; iter < cfg.iters; ++iter) {
            cudaEvent_t start = nullptr;
            cudaEvent_t stop = nullptr;
            check_cuda(cudaEventCreate(&start), "cudaEventCreate(start)");
            check_cuda(cudaEventCreate(&stop), "cudaEventCreate(stop)");
            check_cuda(cudaEventRecord(start), "cudaEventRecord(start)");
            tiny_mnk_gemm_kernel<<<grid, block>>>(dev_a, dev_b, dev_c, cfg.m, cfg.n, cfg.k);
            check_cuda(cudaEventRecord(stop), "cudaEventRecord(stop)");
            check_cuda(cudaEventSynchronize(stop), "cudaEventSynchronize(stop)");

            float latency_ms = 0.0f;
            check_cuda(cudaEventElapsedTime(&latency_ms, start, stop), "cudaEventElapsedTime");
            check_cuda(cudaEventDestroy(start), "cudaEventDestroy(start)");
            check_cuda(cudaEventDestroy(stop), "cudaEventDestroy(stop)");

            out << cfg.label << ','
                << cfg.m << ','
                << cfg.n << ','
                << cfg.k << ','
                << iter << ','
                << latency_ms << ','
                << gflops_for(cfg.m, cfg.n, cfg.k, latency_ms) << ','
                << block.x << ','
                << block.y << ','
                << grid.x << ','
                << grid.y << ','
                << "ok\n";
        }

        check_cuda(cudaFree(dev_a), "cudaFree(A)");
        check_cuda(cudaFree(dev_b), "cudaFree(B)");
        check_cuda(cudaFree(dev_c), "cudaFree(C)");
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "tiny_mnk_bench failed: " << exc.what() << '\n';
        return 1;
    }
}
