from __future__ import annotations

from pathlib import Path


QAOA_RING4 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
h q[0];
h q[1];
h q[2];
h q[3];
cx q[0],q[1];
rz(pi/3) q[1];
cx q[0],q[1];
cx q[1],q[2];
rz(pi/3) q[2];
cx q[1],q[2];
cx q[2],q[3];
rz(pi/3) q[3];
cx q[2],q[3];
cx q[3],q[0];
rz(pi/3) q[0];
cx q[3],q[0];
rx(pi/4) q[0];
rx(pi/4) q[1];
rx(pi/4) q[2];
rx(pi/4) q[3];
"""

GRID_SHAPE6 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[6];
u3(pi/5,pi/7,pi/9) q[0];
rx(pi/6) q[1];
rz(pi/4) q[2];
ry(pi/8) q[3];
h q[4];
u3(pi/10,pi/12,pi/14) q[5];
cx q[0],q[1];
cx q[1],q[2];
cx q[3],q[4];
cx q[4],q[5];
rz(pi/5) q[1];
ry(pi/7) q[4];
cx q[0],q[3];
cx q[1],q[4];
cx q[2],q[5];
rx(pi/11) q[0];
rz(pi/13) q[2];
u3(pi/6,pi/8,pi/10) q[5];
"""


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "workloads" / "sources" / "openqasm"
    root.mkdir(parents=True, exist_ok=True)
    (root / "qaoa_ring4.qasm").write_text(QAOA_RING4, encoding="utf-8")
    (root / "grid_shape6.qasm").write_text(GRID_SHAPE6, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
