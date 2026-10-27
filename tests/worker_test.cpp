#include "job_system/worker.h"

#include <cassert>
#include <memory>
#include <sstream>
#include <string>

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

    assert(logs.find("worker=1") != std::string::npos);
    assert(logs.find("job=1") != std::string::npos);
    assert(logs.find("START") != std::string::npos);
    assert(logs.find("status=COMPLETED") != std::string::npos);

    assert(queue.empty());

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

    return 0;
}