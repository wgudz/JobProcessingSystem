#include "job_system/worker.h"

#include <stdexcept>
#include <exception>

Worker::Worker(
    ThreadSafeQueue<std::shared_ptr<Job>>& queue,
    Logger& logger,
    Statistics& statistics,
    std::size_t workerId
)
    : queue_(queue),
      logger_(logger),
      statistics_(statistics),
      workerId_(workerId)
{
}

Worker::~Worker()
{
    stopRequested_ = true;

    queue_.notifyAll();

    join();
}

void Worker::start()
{
    if (thread_.joinable())
    {
        throw std::logic_error("Worker is already running");
    }

    thread_ = std::thread(
        [this]()
        {
            try
            {
                run();
            }
            catch (...)
            {

            }
        }
    );
}

void Worker::run()
{
    while (true)
    {
        auto job = queue_.waitAndPop(stopRequested_);

        if (!job.has_value())
        {
            break;
        }
        
        try
        {
            logger_.log(
                LogLevel::Info,
                workerId_,
                job.value()->id(),
                "START"
            );
        }
        catch (...)
        {

        }

        const auto executionStart =
            std::chrono::steady_clock::now();

        const auto waitTime =
            std::chrono::duration_cast<std::chrono::milliseconds>(
                executionStart - job.value()->queuedAt()
            );

        try
        {
            executor_.execute(*job.value());
        }
        catch (const std::exception& e)
        {
            job.value()->setError(e.what());
            job.value()->setStatus(JobStatus::Failed);
        }
        catch (...)
        {
            job.value()->setError("Unknown execution error");
            job.value()->setStatus(JobStatus::Failed);
        }

        const auto executionEnd =
            std::chrono::steady_clock::now();

        const auto executionTime =
            std::chrono::duration_cast<std::chrono::milliseconds>(
                executionEnd - executionStart
            );

        std::string statusText;

        const auto status = job.value()->status();

        if (job.value()->markStatisticsRecorded())
        {
            if (status == JobStatus::Completed)
            {
                statistics_.recordCompleted(
                    waitTime,
                    executionTime
                );
            }
            else if (status == JobStatus::Failed)
            {
                statistics_.recordFailed(
                    waitTime,
                    executionTime
                );
            }
            else if (status == JobStatus::Cancelled)
            {
                statistics_.recordCancelled(
                    waitTime,
                    executionTime
                );
            }
            else if (status == JobStatus::TimedOut)
            {
                statistics_.recordTimedOut(
                    waitTime,
                    executionTime
                );
            }
        }
        switch (status)
        {
            case JobStatus::Completed:
                statusText = "COMPLETED";
                break;

            case JobStatus::Failed:
                statusText = "FAILED";
                break;

            case JobStatus::Cancelled:
                statusText = "CANCELLED";
                break;

            case JobStatus::TimedOut:
                statusText = "TIMED_OUT";
                break;

            case JobStatus::Running:
                statusText = "RUNNING";
                break;

            case JobStatus::Queued:
                statusText = "QUEUED";
                break;
        }

        try
        {
            logger_.log(
                LogLevel::Info,
                workerId_,
                job.value()->id(),
                "status=" + statusText
            );
        }
        catch (...)
        {
        }
    }
}
void Worker::join()
{
    if (thread_.joinable())
    {
        thread_.join();
    }
}