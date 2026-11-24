---
name: job-concurrency-review
description: Review JobProcessingSystem changes that may affect multithreaded correctness, state transitions, wake-ups, cancellation, timeouts, worker stop and statistics accounting.
---
# Job concurrency review

Use this Skill for code review of an existing JobProcessingSystem change when the diff may affect multithreaded correctness. Do not teach `std::mutex` or general threading theory. Review the concrete change against the repository's existing contracts and evidence.

## Scope

Review only concurrency-sensitive behaviour that the current diff can affect:

- Job state transitions, especially whether a terminal state can be overwritten later;
- `ThreadSafeQueue<T>::waitAndPop()` and the overload taking `stopRequested`;
- `ThreadSafeQueue<T>::close()`, `notifyAll()` and queue wake-up behaviour;
- the worker-stop path and its interaction with `stopRequested`;
- cancellation and timeout paths;
- whether a cancelled job can still be dequeued or executed;
- whether a timed-out job can later become completed;
- statistics finalization through existing functions such as `Statistics::recordCompleted`, `recordFailed`, `recordCancelled` and `recordTimedOut`;
- double counting of one terminal outcome;
- timing-dependent tests and scheduler dependence.

The repository contains `include/job_system/thread_safe_queue.h`, `src/job.cpp`, `src/worker.cpp`, `src/worker_pool.cpp`, `src/job_manager.cpp`, `src/statistics.cpp`, `tests/thread_safe_queue_test.cpp` and `tests/cancellation_timeout_test.cpp`. Do not invent additional APIs. Before naming a function that is not listed above, locate the real symbol with `search_code` or `read_file`.

## Review order

1. Inspect repository state and the current `git_diff` first. The diff defines the review scope.
2. Identify every changed shared datum, state transition, wait predicate, notification, stop/cancel/timeout path or statistics update.
3. Read the affected implementation or use `search_code` to obtain the surrounding existing contract. Do not report unrelated pre-existing code as a finding.
4. If an existing focused test maps to the changed module and execution is allowed, run it as supporting evidence. A passing test does not erase a code-level concurrency violation demonstrated by the diff.
5. Produce findings only when they are connected to changed lines and repository evidence.

For a documentation-only diff, state that executable behaviour was not changed. Do not invent a deadlock, race condition, lost notification or invalid state transition.

## Data and lock checklist

For each affected shared datum or state, answer all applicable questions:

- Who writes it?
- Who reads it?
- Is every conflicting access protected by the same mutex or by a suitable atomic operation?
- If more than one lock may be held, is there one consistent lock order on all relevant paths?
- Can a callback, wait or notification happen while a lock is held in a way that creates a cycle or stalls progress?
- Is the condition checked under the same lock that protects the condition state?
- Can a state observed as terminal be changed again later?
- Can two paths both finalize the same job and both update statistics?

Do not call something a race merely because multiple threads exist. Name the shared datum, conflicting accesses and missing synchronization.

## Job state invariants

Treat COMPLETED, FAILED, CANCELLED and TIMED_OUT as terminal outcomes for review purposes. Check changed code for paths that could:

- write another status after a terminal outcome;
- allow work to continue after cancellation without the repository's cooperative-stop rules;
- dequeue or execute a job that has already been cancelled;
- mark a job COMPLETED after it has already timed out;
- record two different terminal statistics for the same job.

If the exact status-changing function name is not present in evidence, describe the transition without inventing a symbol.

## Queue and worker invariants

For changes around `ThreadSafeQueue` and worker shutdown, check:

- the `waitAndPop` predicate and the state that makes it wake;
- whether `close()` changes the state seen by waiters and wakes all waiters that must re-check it;
- whether `notifyAll()` or another existing notification path can be lost by the changed code;
- whether `stopRequested` can make a waiting worker leave promptly;
- whether a stop/cancel path can still permit a queued job to be returned and executed;
- whether queue state and stop state are checked in an order that matches the existing contract.

A removed or bypassed wake-up that leaves a waiter blocked even though the predicate state changed is a contract violation when the surrounding code proves that waiter relies on that notification.

## Statistics invariants

The existing statistics functions increment a terminal counter and `finishedJobs_`. Review changed finalization paths for exactly-once accounting:

- one job must not call two terminal `record*` functions;
- retry/cancel/timeout paths must not count the same job twice;
- a transition from TIMED_OUT or CANCELLED to COMPLETED must not produce a second terminal count;
- a mutex around the counters does not by itself prevent logical double counting from two serialized paths.

## Time-dependent tests

Treat a test as scheduler-dependent when correctness depends on a thread reaching a point merely because the test slept for an assumed duration.

Flag a timing test when:

- `sleep_for` or an elapsed-time delay is used to assume that another thread has already reached a wait, state transition or cancellation point;
- pass/fail depends on OS scheduling, machine load or a narrow timing window;
- the test has no observable synchronization proving the required ordering.

Prefer explicit synchronization already suitable for the test: an atomic handshake, condition variable, latch/barrier where available, or another observable state transition. A sleep can remain as workload or timeout duration, but it should not be the only proof that thread A reached a required point before thread B acts.

Do not call a timing test deterministic merely because it passed once.

## Required edge cases

Always consider these when the diff touches the related path:

- the same terminal job counted twice;
- `close()` changes state but required waiters do not receive the wake-up they rely on;
- a job is taken from the queue after cancellation;
- a job reaches COMPLETED after TIMED_OUT;
- worker stop and queue close happen concurrently;
- cancellation/timeout and normal completion race to finalize the same job.

Do not force these findings into unrelated diffs. They are review questions, not presumed bugs.

## Risk classification

Use exactly one of the following phrases in `## Risks`.

**`Pewne naruszenie kontraktu:`** use only when repository evidence demonstrates that the changed code violates an invariant. State the concrete changed line/path, the existing contract it breaks, and the observable consequence.

**`Możliwy race condition:`** use when the diff creates a plausible unsafe interleaving but the available evidence does not prove that the conflicting path is reachable or that synchronization is absent in all relevant code. State exactly what evidence is missing.

**`Brak wystarczających dowodów:`** use when the diff and inspected context do not support a concurrency defect. For a documentation-only change, explicitly state that executable code was not changed and do not speculate about deadlocks or races.

Never upgrade uncertainty into a confirmed violation because a test is flaky, because code "looks suspicious", or because multiple threads exist.

## Final report

Use exactly these headings:

## Facts

Describe only repository-backed facts and cite the relevant `EVID-*` identifiers.

## Hypotheses

Describe only mechanisms not yet proven. If the violation is already demonstrated directly by the diff and existing code, say that no additional race hypothesis is needed.

## Minimal fix

For a confirmed or plausible finding, describe the smallest change that restores the existing contract. Do not apply it. For no supported defect, state that no source fix is justified.

## Test plan

Name the focused test when one exists. For concurrency timing behaviour, state whether the test needs explicit synchronization instead of relying only on `sleep`. Do not claim a test was executed unless evidence shows it.

## Risks

Start with exactly one required risk phrase and keep the wording consistent with its evidence threshold.

## Final result

Summarize the review outcome and whether the change should be blocked, needs more evidence, or has no concurrency-relevant finding.
