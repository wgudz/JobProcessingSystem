#include "job_system/job_manager.h"

#include <stdexcept>

JobManager::JobManager(std::size_t workerCount)
    : workerPool_(workerCount)
{
}

Job::Id JobManager::submit(
    JobType type,
    JobPriority priority,
    std::int64_t input,
    std::optional<std::chrono::milliseconds> timeout
)
{
    Job::Id id;

    {
        std::lock_guard<std::mutex> lock(mutex_);
        id = nextId_++;
    }

    auto job = std::make_shared<Job>(
        id,
        type,
        priority,
        input
    );

    if (timeout.has_value())
    {
        job->setTimeout(timeout.value());
    }

    {
        std::lock_guard<std::mutex> lock(mutex_);
        jobs_.emplace(id, job);
    }

    if (!workerPool_.submit(job))
    {
        std::lock_guard<std::mutex> lock(mutex_);
        jobs_.erase(id);

        throw std::runtime_error(
            "System is shutting down"
        );
    }

    return id;
}

void JobManager::start()
{
    workerPool_.start();
}

void JobManager::stop()
{
    workerPool_.stop();
}

JobStatus JobManager::status(Job::Id id) const
{
    std::shared_ptr<Job> job;

    {
        std::lock_guard<std::mutex> lock(mutex_);

        const auto it = jobs_.find(id);

        if (it == jobs_.end())
        {
            throw std::out_of_range("Job not found");
        }

        job = it->second;
    }

    return job->status();
}

std::optional<std::string> JobManager::result(Job::Id id) const
{
    std::shared_ptr<Job> job;

    {
        std::lock_guard<std::mutex> lock(mutex_);

        const auto it = jobs_.find(id);

        if (it == jobs_.end())
        {
            throw std::out_of_range("Job not found");
        }

        job = it->second;
    }

    return job->result();
}

std::optional<std::string> JobManager::error(Job::Id id) const
{
    std::shared_ptr<Job> job;

    {
        std::lock_guard<std::mutex> lock(mutex_);

        const auto it = jobs_.find(id);

        if (it == jobs_.end())
        {
            throw std::out_of_range("Job not found");
        }

        job = it->second;
    }

    return job->error();
}

bool JobManager::cancel(Job::Id id)
{
    std::shared_ptr<Job> job;

    {
        std::lock_guard<std::mutex> lock(mutex_);

        const auto it = jobs_.find(id);

        if (it == jobs_.end())
        {
            return false;
        }

        job = it->second;
    }

    const auto result = job->requestCancel();

    if (result == CancelResult::Rejected)
    {
        return false;
    }

    if (result == CancelResult::CancelledBeforeStart)
    {
        if (job->markStatisticsRecorded())
        {
            const auto waitTime =
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - job->queuedAt()
                );

            workerPool_.statistics().recordCancelled(
                waitTime,
                std::chrono::milliseconds(0)
            );
        }
    }

    return true;
}

const Statistics& JobManager::statistics() const
{
    return workerPool_.statistics();
}
