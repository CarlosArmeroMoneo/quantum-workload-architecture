PRAGMA enable_progress_bar=false;

-- Note: DuckDB does not support cross-schema foreign keys.
-- Logical relationships are preserved by column naming and application checks in this scaffold.

CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS corpus;
CREATE SCHEMA IF NOT EXISTS features;
CREATE SCHEMA IF NOT EXISTS planning;
CREATE SCHEMA IF NOT EXISTS execution;
CREATE SCHEMA IF NOT EXISTS profiling;
CREATE SCHEMA IF NOT EXISTS arch;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE IF NOT EXISTS meta.schema_registry (
    schema_version VARCHAR PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS meta.system_profile (
    system_id VARCHAR PRIMARY KEY,
    hostname_hash VARCHAR NOT NULL,
    node_label VARCHAR,
    gpu_model VARCHAR,
    gpu_count INTEGER NOT NULL CHECK (gpu_count >= 0),
    gpu_mem_gb DOUBLE,
    gpu_present BOOLEAN NOT NULL DEFAULT FALSE,
    cupy_present BOOLEAN NOT NULL DEFAULT FALSE,
    cuquantum_present BOOLEAN NOT NULL DEFAULT FALSE,
    qiskit_present BOOLEAN NOT NULL DEFAULT FALSE,
    nsys_present BOOLEAN NOT NULL DEFAULT FALSE,
    ncu_present BOOLEAN NOT NULL DEFAULT FALSE,
    cpu_model VARCHAR,
    cpu_sockets INTEGER,
    cpu_cores_logical INTEGER,
    ram_gb DOUBLE,
    driver_version VARCHAR,
    cuda_version VARCHAR,
    cuquantum_sdk_version VARCHAR,
    cuquantum_python_version VARCHAR,
    cudaq_version VARCHAR,
    appliance_tag VARCHAR,
    nsight_systems_version VARCHAR,
    nsight_compute_version VARCHAR,
    mpi_impl VARCHAR,
    os_release VARCHAR,
    container_runtime VARCHAR,
    captured_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS meta.dataset_registry (
    dataset_id VARCHAR PRIMARY KEY,
    project VARCHAR NOT NULL CHECK (project IN ('foundation', 'atlas', 'tnep', 'arch')),
    dataset_name VARCHAR NOT NULL,
    version_tag VARCHAR NOT NULL,
    description VARCHAR,
    split_policy VARCHAR,
    manifest_path VARCHAR,
    frozen_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    UNIQUE(project, dataset_name, version_tag)
);

CREATE TABLE IF NOT EXISTS corpus.workload_spec (
    workload_id VARCHAR PRIMARY KEY,
    dataset_id VARCHAR,
    family_id VARCHAR NOT NULL CHECK (family_id IN (
        'dense_universal',
        'qaoa_graph',
        'trotter_1d',
        'grid_2d_shallow',
        'noisy_observable',
        'qec_clifford',
        'repeated_sweep'
    )),
    family_version VARCHAR NOT NULL,
    source_format VARCHAR NOT NULL CHECK (source_format IN ('qiskit', 'cirq', 'stim', 'cudaq', 'normalized_ir')),
    semantic_target VARCHAR NOT NULL CHECK (semantic_target IN (
        'state', 'amplitude', 'batched_amplitudes', 'expectation', 'samples', 'detectors', 'syndrome_summary'
    )),
    generator_name VARCHAR NOT NULL,
    generator_version VARCHAR NOT NULL,
    seed BIGINT,
    parameter_json JSON NOT NULL,
    repeat_count_hint INTEGER NOT NULL DEFAULT 1 CHECK (repeat_count_hint >= 1),
    reference_tier VARCHAR NOT NULL CHECK (reference_tier IN ('smoke', 'exact_ref', 'boundary', 'scale')),
    split_tag VARCHAR NOT NULL CHECK (split_tag IN ('train', 'val', 'test', 'heldout_family', 'demo')),
    source_hash VARCHAR NOT NULL,
    source_descriptor_json JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS corpus.normalized_ir (
    workload_id VARCHAR PRIMARY KEY,
    schema_version VARCHAR NOT NULL,
    n_qubits INTEGER NOT NULL CHECK (n_qubits > 0),
    depth INTEGER NOT NULL CHECK (depth >= 0),
    moments INTEGER NOT NULL CHECK (moments >= 0),
    gate_hist_json JSON NOT NULL,
    two_qubit_density DOUBLE CHECK (two_qubit_density >= 0.0 AND two_qubit_density <= 1.0),
    non_clifford_fraction DOUBLE CHECK (non_clifford_fraction >= 0.0 AND non_clifford_fraction <= 1.0),
    clifford_valid BOOLEAN NOT NULL,
    measurement_count INTEGER NOT NULL DEFAULT 0 CHECK (measurement_count >= 0),
    reset_count INTEGER NOT NULL DEFAULT 0 CHECK (reset_count >= 0),
    noise_json JSON,
    observable_json JSON,
    execution_target_json JSON,
    interaction_graph_json JSON,
    source_summary_json JSON,
    ir_hash VARCHAR NOT NULL UNIQUE,
    normalized_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS corpus.workload_asset (
    workload_id VARCHAR NOT NULL,
    asset_role VARCHAR NOT NULL CHECK (asset_role IN ('source', 'normalized_ir', 'reference_output', 'demo_input')),
    asset_id VARCHAR NOT NULL,
    PRIMARY KEY (workload_id, asset_role)
);

CREATE TABLE IF NOT EXISTS features.feature_snapshot (
    feature_id VARCHAR PRIMARY KEY,
    workload_id VARCHAR NOT NULL,
    extractor_version VARCHAR NOT NULL,
    static_features_json JSON NOT NULL,
    graph_features_json JSON NOT NULL,
    statevec_mem_est_fp32_bytes BIGINT,
    statevec_mem_est_fp64_bytes BIGINT,
    family_label VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    UNIQUE (workload_id, extractor_version)
);

CREATE TABLE IF NOT EXISTS planning.probe_observation (
    probe_id VARCHAR PRIMARY KEY,
    workload_id VARCHAR NOT NULL,
    system_id VARCHAR,
    project VARCHAR NOT NULL CHECK (project IN ('atlas', 'tnep', 'arch')),
    probe_kind VARCHAR NOT NULL CHECK (probe_kind IN ('tn_contract_path', 'tn_workspace_probe', 'mps_pilot', 'sv_mem_probe', 'distributed_probe')),
    mode VARCHAR NOT NULL CHECK (mode IN ('statevec', 'statevec_mgpu', 'exact_tn', 'mps', 'exact_tn_distributed', 'pauliprop', 'stabilizer')),
    objective VARCHAR CHECK (objective IN ('ttfr', 'steady_state', 'gpu_seconds')),
    precision VARCHAR CHECK (precision IN ('fp32', 'fp64', 'complex64', 'complex128')),
    workspace_gb DOUBLE,
    cache_workspace_gb DOUBLE,
    hyper_samples INTEGER,
    autotune BOOLEAN,
    reuse_cache BOOLEAN,
    mpi_ranks INTEGER,
    gpu_arch_target VARCHAR,
    predicted_peak_gb DOUBLE,
    predicted_error DOUBLE,
    optimizer_cost DOUBLE,
    largest_intermediate DOUBLE,
    num_slices INTEGER,
    raw_info_json JSON,
    status VARCHAR NOT NULL CHECK (status IN ('success', 'unsupported', 'probe_fail', 'timeout')),
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS planning.plan_candidate (
    plan_id VARCHAR PRIMARY KEY,
    workload_id VARCHAR NOT NULL,
    project VARCHAR NOT NULL CHECK (project IN ('atlas', 'tnep', 'arch')),
    planner_version VARCHAR NOT NULL,
    objective VARCHAR NOT NULL CHECK (objective IN ('ttfr', 'steady_state', 'gpu_seconds')),
    mode VARCHAR NOT NULL CHECK (mode IN ('statevec', 'statevec_mgpu', 'exact_tn', 'mps', 'exact_tn_distributed', 'pauliprop', 'stabilizer')),
    precision VARCHAR CHECK (precision IN ('fp32', 'fp64', 'complex64', 'complex128')),
    workspace_gb DOUBLE,
    cache_workspace_gb DOUBLE,
    hyper_samples INTEGER,
    autotune BOOLEAN,
    reuse_cache BOOLEAN,
    mpi_ranks INTEGER,
    gpu_arch_target VARCHAR,
    max_error DOUBLE,
    predicted_ttfr_s DOUBLE,
    predicted_iter_ms DOUBLE,
    predicted_peak_gb DOUBLE,
    predicted_error DOUBLE,
    feasibility_label VARCHAR NOT NULL CHECK (feasibility_label IN ('feasible', 'infeasible', 'uncertain', 'abstain')),
    explanation_json JSON NOT NULL,
    parent_probe_ids JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);


CREATE TABLE IF NOT EXISTS planning.validation_run (
    validation_run_id VARCHAR PRIMARY KEY,
    project VARCHAR NOT NULL CHECK (project IN ('atlas', 'tnep', 'arch')),
    planner_version VARCHAR NOT NULL,
    manifest_path VARCHAR,
    objective VARCHAR NOT NULL CHECK (objective IN ('ttfr', 'steady_state', 'gpu_seconds')),
    evaluation_source VARCHAR NOT NULL CHECK (evaluation_source IN ('surrogate_oracle', 'measured')),
    workload_count INTEGER NOT NULL CHECK (workload_count >= 0),
    heldout_workload_count INTEGER NOT NULL CHECK (heldout_workload_count >= 0),
    top1_accuracy DOUBLE,
    mean_regret DOUBLE,
    heldout_mean_regret DOUBLE,
    summary_json JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS planning.plan_evaluation (
    evaluation_id VARCHAR PRIMARY KEY,
    validation_run_id VARCHAR,
    plan_id VARCHAR NOT NULL,
    workload_id VARCHAR NOT NULL,
    evaluation_source VARCHAR NOT NULL CHECK (evaluation_source IN ('surrogate_oracle', 'measured')),
    split_tag VARCHAR,
    family_id VARCHAR,
    objective VARCHAR NOT NULL CHECK (objective IN ('ttfr', 'steady_state', 'gpu_seconds')),
    status VARCHAR NOT NULL CHECK (status IN ('success', 'infeasible', 'invalid', 'abstain')),
    feasible BOOLEAN NOT NULL,
    observed_ttfr_s DOUBLE,
    observed_iter_ms DOUBLE,
    observed_peak_gb DOUBLE,
    observed_gpu_seconds DOUBLE,
    observed_error DOUBLE,
    oracle_rank INTEGER,
    regret DOUBLE,
    normalized_regret DOUBLE,
    details_json JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS execution.execution_run (
    run_id VARCHAR PRIMARY KEY,
    plan_id VARCHAR NOT NULL,
    workload_id VARCHAR NOT NULL,
    system_id VARCHAR NOT NULL,
    replicate_idx INTEGER NOT NULL DEFAULT 0,
    status VARCHAR NOT NULL CHECK (status IN (
        'success', 'oom', 'unsupported_semantics', 'error_budget_fail', 'planner_fail', 'timeout', 'mpi_fail', 'runtime_error'
    )),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    wall_s DOUBLE,
    ttfr_s DOUBLE,
    steady_iter_ms DOUBLE,
    gpu_seconds DOUBLE,
    peak_mem_gb DOUBLE,
    peak_workspace_gb DOUBLE,
    output_digest VARCHAR,
    execution_source VARCHAR,
    failure_detail_json JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    UNIQUE (plan_id, system_id, replicate_idx)
);

CREATE TABLE IF NOT EXISTS execution.accuracy_eval (
    eval_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    reference_run_id VARCHAR,
    metric_name VARCHAR NOT NULL CHECK (metric_name IN (
        'l2', 'infidelity', 'observable_abs_err', 'observable_rel_err', 'syndrome_match_rate', 'bitstring_prob_abs_err',
        'amplitude_abs_err', 'amplitude_rel_err', 'batched_amplitude_max_abs_err'
    )),
    metric_value DOUBLE NOT NULL,
    threshold DOUBLE,
    pass BOOLEAN,
    evaluation_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS profiling.profile_summary (
    profile_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    profiler_kind VARCHAR NOT NULL CHECK (profiler_kind IN ('nsys', 'ncu', 'both', 'synthetic')),
    nvtx_phase_times_json JSON,
    top_kernels_json JSON,
    dram_util_pct DOUBLE,
    sm_util_pct DOUBLE,
    occupancy_pct DOUBLE,
    comm_time_pct DOUBLE,
    nsys_asset_id VARCHAR,
    ncu_asset_id VARCHAR,
    profile_version VARCHAR NOT NULL,
    derived_signals_json JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS profiling.asset_index (
    asset_id VARCHAR PRIMARY KEY,
    asset_type VARCHAR NOT NULL CHECK (asset_type IN (
        'qpy', 'stim', 'json', 'yaml', 'parquet', 'duckdb', 'nsys-rep', 'ncu-rep', 'png', 'svg', 'pdf', 'md', 'sqlite', 'csv'
    )),
    relative_path VARCHAR NOT NULL,
    sha256 VARCHAR,
    size_bytes BIGINT,
    tracked_in_git BOOLEAN NOT NULL DEFAULT FALSE,
    notes VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS execution.run_asset (
    run_id VARCHAR NOT NULL,
    asset_role VARCHAR NOT NULL CHECK (asset_role IN (
        'raw_execution_json', 'raw_accuracy_json', 'reference_output_json', 'profile_summary_json', 'profiler_attempt_json'
    )),
    asset_id VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (run_id, asset_role, asset_id)
);

CREATE TABLE IF NOT EXISTS profiling.profile_asset (
    profile_id VARCHAR NOT NULL,
    asset_role VARCHAR NOT NULL CHECK (asset_role IN (
        'raw_profile_json', 'nsys_report', 'nsys_sqlite', 'nsys_stats_csv', 'ncu_report', 'ncu_csv'
    )),
    asset_id VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (profile_id, asset_role, asset_id)
);

CREATE TABLE IF NOT EXISTS profiling.profiler_attempt (
    attempt_id VARCHAR PRIMARY KEY,
    run_id VARCHAR,
    tool_kind VARCHAR NOT NULL CHECK (tool_kind IN ('nsys', 'ncu')),
    attempt_role VARCHAR NOT NULL CHECK (attempt_role IN ('profile', 'smoke', 'readiness')),
    tool_version VARCHAR,
    importer_version VARCHAR,
    command_json JSON NOT NULL,
    exit_code INTEGER,
    stdout_digest VARCHAR,
    stderr_digest VARCHAR,
    stderr_excerpt VARCHAR,
    failure_class VARCHAR,
    usability_state VARCHAR NOT NULL,
    state_json JSON NOT NULL,
    artifact_presence_json JSON NOT NULL,
    remediation_json JSON,
    notes VARCHAR,
    attempt_asset_id VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS arch.bottleneck_case (
    case_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    bottleneck_family VARCHAR NOT NULL CHECK (bottleneck_family IN (
        'memory_capacity', 'memory_bandwidth', 'planner_roi', 'communication', 'launch_overhead', 'reuse_cache'
    )),
    nomination_reason_json JSON NOT NULL,
    supporting_profile_ids JSON,
    accepted_for_study BOOLEAN NOT NULL DEFAULT FALSE,
    severity_score DOUBLE,
    nomination_source VARCHAR,
    counterfactual_hypotheses_json JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS arch.counterfactual_result (
    cf_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    knob_name VARCHAR NOT NULL,
    knob_value DOUBLE NOT NULL,
    knob_unit VARCHAR,
    model_version VARCHAR NOT NULL,
    predicted_ttfr_s DOUBLE,
    predicted_iter_ms DOUBLE,
    predicted_peak_gb DOUBLE,
    predicted_gpu_seconds DOUBLE,
    predicted_boundary_shift_json JSON,
    validation_json JSON,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);


CREATE VIEW IF NOT EXISTS marts.latest_validation_runs AS
SELECT
    validation_run_id,
    project,
    planner_version,
    objective,
    workload_count,
    heldout_workload_count,
    top1_accuracy,
    mean_regret,
    heldout_mean_regret,
    row_number() OVER (
        PARTITION BY project, objective
        ORDER BY created_at DESC
    ) AS recency_rank
FROM planning.validation_run;

CREATE VIEW IF NOT EXISTS marts.plan_evaluation_summary AS
SELECT
    validation_run_id,
    objective,
    count(*) AS evaluation_count,
    avg(regret) AS avg_regret,
    avg(normalized_regret) AS avg_normalized_regret,
    sum(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_candidates
FROM planning.plan_evaluation
GROUP BY validation_run_id, objective;


CREATE VIEW IF NOT EXISTS marts.profile_phase_overview AS
SELECT
    p.profile_id,
    p.run_id,
    p.profiler_kind,
    p.comm_time_pct,
    p.dram_util_pct,
    p.sm_util_pct,
    p.occupancy_pct,
    p.derived_signals_json
FROM profiling.profile_summary p;

CREATE VIEW IF NOT EXISTS marts.latest_successful_runs AS
SELECT
    r.run_id,
    r.workload_id,
    r.system_id,
    r.wall_s,
    r.ttfr_s,
    r.steady_iter_ms,
    r.gpu_seconds,
    r.peak_mem_gb,
    p.mode,
    p.objective,
    p.planner_version,
    p.feasibility_label,
    row_number() OVER (
        PARTITION BY r.workload_id, r.system_id, p.mode, p.objective
        ORDER BY r.created_at DESC
    ) AS recency_rank
FROM execution.execution_run r
JOIN planning.plan_candidate p ON p.plan_id = r.plan_id
WHERE r.status = 'success';

CREATE VIEW IF NOT EXISTS marts.plan_regret_inputs AS
SELECT
    p.plan_id,
    p.workload_id,
    p.mode,
    p.objective,
    p.predicted_ttfr_s,
    p.predicted_iter_ms,
    p.predicted_peak_gb,
    r.wall_s,
    r.ttfr_s,
    r.steady_iter_ms,
    r.peak_mem_gb,
    r.status
FROM planning.plan_candidate p
LEFT JOIN execution.execution_run r ON r.plan_id = p.plan_id;


CREATE VIEW IF NOT EXISTS marts.plan_prediction_error AS
SELECT
    p.plan_id,
    p.workload_id,
    p.mode,
    p.objective,
    r.execution_source,
    p.predicted_ttfr_s,
    r.ttfr_s,
    (r.ttfr_s - p.predicted_ttfr_s) AS ttfr_residual_s,
    p.predicted_iter_ms,
    r.steady_iter_ms,
    (r.steady_iter_ms - p.predicted_iter_ms) AS iter_residual_ms,
    p.predicted_peak_gb,
    r.peak_mem_gb,
    (r.peak_mem_gb - p.predicted_peak_gb) AS peak_residual_gb,
    r.status
FROM planning.plan_candidate p
JOIN execution.execution_run r ON r.plan_id = p.plan_id;


CREATE VIEW IF NOT EXISTS marts.bottleneck_nomination_summary AS
SELECT
    bottleneck_family,
    count(*) AS nomination_count,
    avg(severity_score) AS mean_severity,
    sum(CASE WHEN accepted_for_study THEN 1 ELSE 0 END) AS accepted_count
FROM arch.bottleneck_case
GROUP BY bottleneck_family;
