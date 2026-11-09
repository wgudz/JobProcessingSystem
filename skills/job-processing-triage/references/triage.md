# Investigation checklist

1. Establish baseline SHA, branch, `git status`, compiler/CMake versions.
2. Reproduce by CTest on an unchanged baseline. Record host and number of runs.
3. Induce one *controlled* regression and write down the relevant test failure.
4. Compare `git diff`, CTest output, failed test source, and implementation; do not rely on guesses.
5. Identify if the check is deterministic (e.g., wrong counter) or timing-sensitive (e.g., worker stop race).
6. Only students, after review, patch code on their branch; agent stays read-only.
7. Run CTest again. For concurrency run a repeated CTest pass separately, record duration and failures.
8. State limitations: a passed unit suite cannot prove absence of data races. Sanitizers and stress tests have platform constraints.
9. Write final RCA/PR in five sections: evidence, root cause, smallest change, verification, residual risks.
