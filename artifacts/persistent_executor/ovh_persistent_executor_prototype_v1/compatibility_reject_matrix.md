# Persistent Executor Compatibility Reject Matrix

| Case | Expected | Actual | Passed | Reject Reason |
| --- | --- | --- | --- | --- |
| compatible_control | accepted | accepted | True |  |
| repo_commit_mismatch | persistent_executor_rejected | persistent_executor_rejected | True | request compatibility fingerprint did not match the worker session or the supplied execution payload: repo_commit |
| package_version_mismatch | persistent_executor_rejected | persistent_executor_rejected | True | request compatibility fingerprint did not match the worker session or the supplied execution payload: package_version |
| execution_stack_version_mismatch | persistent_executor_rejected | persistent_executor_rejected | True | request compatibility fingerprint did not match the worker session or the supplied execution payload: execution_stack_version |
| objective_mismatch | persistent_executor_rejected | persistent_executor_rejected | True | request compatibility fingerprint did not match the worker session or the supplied execution payload: objective |
| precision_mismatch | persistent_executor_rejected | persistent_executor_rejected | True | request compatibility fingerprint did not match the worker session or the supplied execution payload: precision |
| system_id_mismatch | persistent_executor_rejected | persistent_executor_rejected | True | request compatibility fingerprint did not match the worker session or the supplied execution payload: system_id |
| selected_plan_id_mismatch | persistent_executor_rejected | persistent_executor_rejected | True | request compatibility fingerprint did not match the worker session or the supplied execution payload: selected_plan_id |
