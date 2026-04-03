def aqs_cudaq_program() -> dict:
    return {
        "api_version": "aqs.cudaq_program.v1",
        "program_name": "cudaq_ghz3",
        "source_kind": "cudaq_kernel_adapter",
        "openqasm2": """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
""",
        "metadata": {
            "authoring_model": "adapter_stub",
            "semantic_note": "adapter-backed CUDA-Q authoring fixture",
        },
    }
