# Known Limitations: Profiler Host Blockers

Current state:
- real exact-TN execution is real and correctness-checked
- profiler artifact generation is not yet complete on the current host stack

Observed blockers:
- Nsight Systems collection can produce `.qdstrm`, but usable `.nsys-rep` conversion is blocked on this host
- Nsight Compute may fail to write a usable `.ncu-rep` when GPU counters are blocked or when no kernels are captured for the requested NVTX-filtered range

Interpretation:
- this is an environment/readiness problem, not evidence that the real exact-TN executor is synthetic
- the next milestone is to make profiler readiness explicit, diagnosable, and warehouse-visible

Required closure condition:
- one real exact-TN run must yield a usable `.nsys-rep`
- one real exact-TN run must yield a usable `.ncu-rep`
- both profiler outputs must be ingested into `profile_summary`
- at least one architecture nomination must be emitted with `nomination_source=\"real_profiler_analysis\"`

