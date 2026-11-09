# Actual architecture verified against wgudz/JobProcessingSystem (main, 2026-11-04)

- CMake C++20 and eleven CTest entries.
- `app/main.cpp`: interactive UI for submit/status/result/cancel/statistics.
- `src/job.cpp`: job state transitions, cancel request, timeout, result and stats idempotency.
- `src/job_executor.cpp`: CalculateSum, Sleep, CountPrimes.
- `include/job_system/thread_safe_queue.h`: condition-variable queue with priority buckets high/normal/low and max capacity; `push`, `waitAndPop`, `close`.
- `src/worker.cpp`: run loop, exception containment, state/status reporting, statistics.
- `src/worker_pool.cpp`: starting/stopping workers, priority mapping, queue lifecycle.
- `src/job_manager.cpp`: job IDs, storage, cancel, result/status access.
- `src/statistics.cpp`: completed/failed/cancelled/timedOut counters and mean durations.
- Focus tests: `tests/thread_safe_queue_test.cpp`, `tests/statistics_test.cpp`, `tests/cancellation_timeout_test.cpp`, `tests/worker_pool_test.cpp`.

Do not assume performance, race freedom, or original baseline test success until actually executed.
