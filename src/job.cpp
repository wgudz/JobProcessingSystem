#include "job_system/job.h"
#include <utility>
#include <stdexcept>

Job::Job(
    Id id,
    JobType type,
    JobPriority priority,
    std::int64_t input
)
    : id_(id),
      type_(type),
      status_(JobStatus::Queued),
      priority_(priority),
      created_at_(std::chrono::system_clock::now()),
      input_(input),
      queuedAt_(std::chrono::steady_clock::now())
{
    if (id == 0)
    {
        throw std::invalid_argument("Job ID cannot be zero");
    }
}

Job::Id Job::id() const
{
    return id_;
}

JobType Job::type() const
{
    return type_;
}

JobStatus Job::status() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return status_;
}

JobPriority Job::priority() const
{
    return priority_;
}

std::chrono::system_clock::time_point Job::createdAt() const
{
    return created_at_;
}

bool Job::setStatus(JobStatus newStatus)
{
    std::lock_guard<std::mutex> lock(mutex_);

    if (
        newStatus == JobStatus::Completed &&
        cancelRequested_
    )
    {
        status_ = JobStatus::Cancelled;
        return false;
    }
    
    bool allowed = false;

    switch (status_)
    {
        case JobStatus::Queued:
            allowed =
                newStatus == JobStatus::Running ||
                newStatus == JobStatus::Cancelled ||
                newStatus == JobStatus::TimedOut;
            break;

        case JobStatus::Running:
            allowed =
                newStatus == JobStatus::Completed ||
                newStatus == JobStatus::Failed ||
                newStatus == JobStatus::Cancelled ||
                newStatus == JobStatus::TimedOut;
            break;

        case JobStatus::Completed:
        case JobStatus::Failed:
        case JobStatus::Cancelled:
        case JobStatus::TimedOut:
            allowed = false;
            break;
    }

    if (!allowed)
    {
        return false;
    }

    if (newStatus == JobStatus::Running)
    {
        startedAt_ = std::chrono::steady_clock::now();
    }
    status_ = newStatus;
    return true;
}

void Job::setResult(std::string result)
{
    std::lock_guard<std::mutex> lock(mutex_);
    result_ = std::move(result);
}

void Job::setError(std::string error)
{
    std::lock_guard<std::mutex> lock(mutex_);
    error_ = std::move(error);
}

std::optional<std::string> Job::result() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return result_;
}

std::optional<std::string> Job::error() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return error_;
}

std::int64_t Job::input() const
{
    return input_;
}

CancelResult Job::requestCancel()
{
    std::lock_guard<std::mutex> lock(mutex_);

    if (status_ == JobStatus::Queued)
    {
        status_ = JobStatus::Cancelled;
        return CancelResult::CancelledBeforeStart;
    }

    if (status_ == JobStatus::Running)
    {
        cancelRequested_ = true;
        return CancelResult::CancellationRequested;
    }

    return CancelResult::Rejected;
}

bool Job::cancelRequested() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return cancelRequested_;
}

void Job::setTimeout(std::chrono::milliseconds timeout)
{
    std::lock_guard<std::mutex> lock(mutex_);
    timeout_ = timeout;
}

bool Job::timedOut() const
{
    std::lock_guard<std::mutex> lock(mutex_);

    if (!timeout_.has_value() || !startedAt_.has_value())
    {
        return false;
    }

    const auto elapsed =
        std::chrono::steady_clock::now() - startedAt_.value();

    return elapsed >= timeout_.value();
}

bool Job::complete(std::string result)
{
    std::lock_guard<std::mutex> lock(mutex_);

    if (status_ != JobStatus::Running)
    {
        return false;
    }

    if (cancelRequested_)
    {
        status_ = JobStatus::Cancelled;
        return false;
    }

    if (timeout_.has_value() && startedAt_.has_value())
    {
        const auto elapsed =
            std::chrono::steady_clock::now() - startedAt_.value();

        if (elapsed >= timeout_.value())
        {
            status_ = JobStatus::TimedOut;
            return false;
        }
    }

    result_ = std::move(result);
    status_ = JobStatus::Completed;

    return true;
}

std::chrono::steady_clock::time_point Job::queuedAt() const
{
    return queuedAt_;
}

bool Job::markStatisticsRecorded()
{
    std::lock_guard<std::mutex> lock(mutex_);

    if (statisticsRecorded_)
    {
        return false;
    }

    statisticsRecorded_ = true;
    return true;
}