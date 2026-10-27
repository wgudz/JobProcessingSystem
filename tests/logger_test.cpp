#include "job_system/logger.h"

#include "test_utils.h"
#include <sstream>
#include <string>
#include <thread>
#include <vector>

int main()
{
    std::ostringstream output;
    Logger logger(output);

    constexpr int workerCount = 4;
    constexpr int messagesPerWorker = 100;

    std::vector<std::thread> threads;

    for (int workerId = 0; workerId < workerCount; ++workerId)
    {
        threads.emplace_back(
            [&logger, workerId]()
            {
                for (int i = 0; i < messagesPerWorker; ++i)
                {
                    logger.log(
                        LogLevel::Info,
                        workerId,
                        i + 1,
                        "test message"
                    );
                }
            }
        );
    }

    for (auto& thread : threads)
    {
        thread.join();
    }

    std::istringstream input(output.str());

    std::string line;
    int lineCount = 0;

    while (std::getline(input, line))
    {
        REQUIRE(line.find("INFO") != std::string::npos);
        REQUIRE(line.find("worker=") != std::string::npos);
        REQUIRE(line.find("job=") != std::string::npos);
        REQUIRE(line.find("test message") != std::string::npos);

        ++lineCount;
    }

    REQUIRE(lineCount == workerCount * messagesPerWorker);

    return 0;
}