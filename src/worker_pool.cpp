#include "job_system/worker_pool.h"
#include <utility>
#include <stdexcept>
#include <iostream>

WorkerPool::WorkerPool(std::size_t workerCount)
    : queue_(
        [](const std::shared_ptr<Job>& job)
        {
            if (job->priority() == JobPriority::High)
            {
                return 2;
            }

            if (job->priority() == JobPriority::Low)
            {
                return 0;
            }

            return 1;
        }
    ),
    logger_(std::cout)
{
    if (workerCount == 0)
    {
        throw std::invalid_argument(
            "WorkerPool must contain at least one worker"
        );
    }

    workers_.reserve(workerCount);

    for (std::size_t i = 0; i < workerCount; ++i)
    {
        workers_.push_back(
            std::make_unique<Worker>(
                queue_,
                logger_,
                statistics_,
                i + 1
            )
        );
    }
}

WorkerPool::~WorkerPool()
{
    stop();
}

void WorkerPool::start()
{
    std::lock_guard<std::mutex> lock(stateMutex_);

    if (state_ == State::Running)
    {
        throw std::logic_error("WorkerPool is already running");
    }

    if (state_ == State::Stopped)
    {
        throw std::logic_error("WorkerPool cannot be restarted");
    }

    try
    {
        for (auto& worker : workers_)
        {
            worker->start();
        }

        state_ = State::Running;
    }
    catch (...)
    {
        queue_.close();

        for (auto& worker : workers_)
        {
            worker->join();
        }

        state_ = State::Stopped;
        throw;
    }
}

bool WorkerPool::submit(std::shared_ptr<Job> job)
{
    if (!job)
    {
        throw std::invalid_argument("Job cannot be null");
    }

    return queue_.push(std::move(job));
}

void WorkerPool::stop()
{
    std::lock_guard<std::mutex> lock(stateMutex_);

    if (state_ == State::Stopped)
    {
        return;
    }

    queue_.close();

    for (auto& worker : workers_)
    {
        worker->join();
    }

    state_ = State::Stopped;
}

const Statistics& WorkerPool::statistics() const
{
    return statistics_;
}

Statistics& WorkerPool::statistics()
{
    return statistics_;
}