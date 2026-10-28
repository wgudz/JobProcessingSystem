#include "job_system/worker.h"

#include "test_utils.h"
#include <memory>
#include <sstream>
#include <string>
#include <fstream>

int main()
{
    ThreadSafeQueue<std::shared_ptr<Job>> queue;

    std::ostringstream output;
    Logger logger(output);

    Statistics statistics;

    Worker worker(
        queue,
        logger,
        statistics,
        1
    );

    worker.start();

    queue.push(
        std::make_shared<Job>(
            1,
            JobType::CalculateSum,
            JobPriority::Normal,
            10
        )
    );

    queue.close();

    worker.join();

    const std::string logs = output.str();

    REQUIRE(logs.find("worker=1") != std::string::npos);
    REQUIRE(logs.find("job=1") != std::string::npos);
    REQUIRE(logs.find("START") != std::string::npos);
    REQUIRE(logs.find("status=COMPLETED") != std::string::npos);

    REQUIRE(queue.empty());

    {
        ThreadSafeQueue<std::shared_ptr<Job>> queue;

        std::ostringstream output;
        Logger logger(output);
        Statistics statistics;

        Worker worker(
            queue,
            logger,
            statistics,
            1
        );

        worker.start();

        queue.close();
    }

    {
        ThreadSafeQueue<std::shared_ptr<Job>> queue;

        std::ostringstream output;
        Logger logger(output);
        Statistics statistics;

        {
            Worker worker(
                queue,
                logger,
                statistics,
                1
            );

            worker.start();

            std::this_thread::sleep_for(
                std::chrono::milliseconds(50)
            );

        }

    }

    {
        ThreadSafeQueue<std::shared_ptr<Job>> queue;

        std::ofstream output;

        output.exceptions(
            std::ios::failbit |
            std::ios::badbit
        );

        Logger logger(output);
        Statistics statistics;

        Worker worker(
            queue,
            logger,
            statistics,
            1
        );

        auto job = std::make_shared<Job>(
            1000,
            JobType::CalculateSum,
            JobPriority::Normal,
            10
        );

        REQUIRE(queue.push(job));

        worker.start();

        for (int i = 0; i < 100; ++i)
        {
            if (job->status() == JobStatus::Completed)
            {
                break;
            }

            std::this_thread::sleep_for(
                std::chrono::milliseconds(5)
            );
        }

        REQUIRE(job->status() == JobStatus::Completed);
        REQUIRE(job->result().has_value());
        REQUIRE(job->result().value() == "55");

        queue.close();
        worker.join();
    }

    return 0;
}