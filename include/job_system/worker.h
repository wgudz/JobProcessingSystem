#pragma once

#include "job_system/job.h"
#include "job_system/job_executor.h"
#include "job_system/thread_safe_queue.h"
#include "job_system/logger.h"
#include "job_system/statistics.h"

#include <cstddef>
#include <thread>
#include <memory>
#include <atomic>

class Worker
{
public:
    Worker(
        ThreadSafeQueue<std::shared_ptr<Job>>& queue,
        Logger& logger,
        Statistics& statistics,
        std::size_t workerId
    );

    ~Worker();

    void start();
    void join();
    
private:
    void run();

    ThreadSafeQueue<std::shared_ptr<Job>>& queue_;
    JobExecutor executor_;
    std::thread thread_;

    Logger& logger_;
    std::size_t workerId_;

    Statistics& statistics_;

    std::atomic<bool> stopRequested_ = false;
};
