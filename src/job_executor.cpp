#include "job_system/job_executor.h"

#include <string>
#include <chrono>
#include <thread>

void JobExecutor::execute(Job& job)
{
    if (!job.setStatus(JobStatus::Running))
    {
        return;
    }

    switch (job.type())
    {
        case JobType::CalculateSum:
        {
            
            const auto n = job.input();

            if (n < 0)
            {
                job.setError("Input cannot be negative");
                job.setStatus(JobStatus::Failed);
                return;
            }

            if (n > 4294967295LL)
            {
                job.setError("Input too large");
                job.setStatus(JobStatus::Failed);
                return;
            }

            std::int64_t sum;

            if (n % 2 == 0)
            {
                sum = (n / 2) * (n + 1);
            }
            else
            {
                sum = n * ((n + 1) / 2);
            }

            job.complete(std::to_string(sum));

            // Cancel mógł przyjść dokładnie po zakończeniu pętli
            if (job.cancelRequested())
            {
                job.setStatus(JobStatus::Cancelled);
                return;
            }
            if (job.timedOut())
            {
                job.setStatus(JobStatus::TimedOut);
                return;
            }

            job.complete(std::to_string(sum));
            break;
        }

        case JobType::Sleep:
        {
            const auto milliseconds = job.input();

            
            if (milliseconds < 0)
            {
                job.setError("Sleep duration cannot be negative");
                job.setStatus(JobStatus::Failed);
                return;
            }

            if (milliseconds > 60000)
            {
                job.setError("Sleep duration too large");
                job.setStatus(JobStatus::Failed);
                return;
            }

            std::int64_t remaining = milliseconds;

            while (remaining > 0)
            {
                if (job.cancelRequested())
                {
                    job.setStatus(JobStatus::Cancelled);
                    return;
                }
                if (job.timedOut())
                {
                    job.setStatus(JobStatus::TimedOut);
                    return;
                }
                const std::int64_t sleepTime =
                    remaining > 10 ? 10 : remaining;

                std::this_thread::sleep_for(
                    std::chrono::milliseconds(sleepTime)
                );

                remaining -= sleepTime;
            }

            if (job.cancelRequested())
            {
                job.setStatus(JobStatus::Cancelled);
                return;
            }
            if (job.timedOut())
            {
                job.setStatus(JobStatus::TimedOut);
                return;
            }

            job.complete("Sleep completed");
            break;
        }

        case JobType::CountPrimes:
        {
            const auto n = job.input();

            if (n < 0)
            {
                job.setError("Input cannot be negative");
                job.setStatus(JobStatus::Failed);
                return;
            }

            if (n > 1000000)
            {
                job.setError("Input too large");
                job.setStatus(JobStatus::Failed);
                return;
            }

            std::int64_t count = 0;

            for (std::int64_t number = 2; number <= n; ++number)
            {
                if (job.cancelRequested())
                {
                    job.setStatus(JobStatus::Cancelled);
                    return;
                }
                if (job.timedOut())
                {
                    job.setStatus(JobStatus::TimedOut);
                    return;
                }

                bool isPrime = true;

                for (std::int64_t divisor = 2;
                    divisor * divisor <= number;
                    ++divisor)
                {
                    if (number % divisor == 0)
                    {
                        isPrime = false;
                        break;
                    }
                }

                if (isPrime)
                {
                    ++count;
                }
            }

            if (job.cancelRequested())
            {
                job.setStatus(JobStatus::Cancelled);
                return;
            }
            if (job.timedOut())
            {
                job.setStatus(JobStatus::TimedOut);
                return;
            }

            job.complete(std::to_string(count));
            break;
        }

        default:
            job.setError("Unsupported job type");
            job.setStatus(JobStatus::Failed);
            break;
    }
}
