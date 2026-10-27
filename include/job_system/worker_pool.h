#pragma once

#include "job_system/job.h"
#include "job_system/thread_safe_queue.h"
#include "job_system/worker.h"
#include "job_system/logger.h"
#include "job_system/statistics.h"

#include <cstddef>
#include <memory>
#include <vector>
#include <mutex>

class WorkerPool
{
public:
    explicit WorkerPool(std::size_t workerCount);
    ~WorkerPool();

    void start();
    bool submit(std::shared_ptr<Job> job);
    void stop();

    const Statistics& statistics() const;
    Statistics& statistics();

private:
    private:
    ThreadSafeQueue<std::shared_ptr<Job>> queue_;
    Logger logger_;
    Statistics statistics_;
    std::vector<std::unique_ptr<Worker>> workers_;

    enum class State
    {
        Created,
        Running,
        Stopped
    };

    std::mutex stateMutex_;
    State state_ = State::Created;
};