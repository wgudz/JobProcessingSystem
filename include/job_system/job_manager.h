#pragma once

#include "job_system/job.h"
#include "job_system/worker_pool.h"
#include "job_system/statistics.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <unordered_map>
#include <optional>
#include <string>
#include <chrono>
#include <mutex>

class JobManager
{
public:
    explicit JobManager(std::size_t workerCount);

    Job::Id submit(
        JobType type,
        JobPriority priority,
        std::int64_t input,
        std::optional<std::chrono::milliseconds> timeout = std::nullopt
    );

    void start();
    void stop();

    JobStatus status(Job::Id id) const;

    std::optional<std::string> result(Job::Id id) const;
    std::optional<std::string> error(Job::Id id) const;

    bool cancel(Job::Id id);

    const Statistics& statistics() const;

    bool remove(Job::Id id);

private:
    mutable std::mutex mutex_;

    WorkerPool workerPool_;
    Job::Id nextId_ = 1;
    std::unordered_map<Job::Id, std::shared_ptr<Job>> jobs_;

    static constexpr std::size_t MaxStoredJobs = 1000;
};