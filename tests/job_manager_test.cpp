#include "job_system/job_manager.h"

#include "test_utils.h"
#include <chrono>
#include <thread>
#include <stdexcept>
#include <algorithm>
#include <mutex>
#include <vector>

int main()
{
    JobManager manager(2);

    manager.start();

    const auto id1 = manager.submit(
        JobType::CalculateSum,
        JobPriority::Normal,
        10
    );

    const auto id2 = manager.submit(
        JobType::CountPrimes,
        JobPriority::High,
        100
    );

    REQUIRE(id1 == 1);
    REQUIRE(id2 == 2);
    REQUIRE(id1 != id2);


    const auto sleepId = manager.submit(
        JobType::Sleep,
        JobPriority::Normal,
        300
    );


    bool observedRunning = false;

    for (int i = 0; i < 100; ++i)
    {
        if (manager.status(sleepId) == JobStatus::Running)
        {
            observedRunning = true;
            break;
        }

        std::this_thread::sleep_for(
            std::chrono::milliseconds(5)
        );
    }

    REQUIRE(observedRunning);

    manager.stop();

    REQUIRE(manager.status(id1) == JobStatus::Completed);
    REQUIRE(manager.status(id2) == JobStatus::Completed);

    const auto result1 = manager.result(id1);
    const auto result2 = manager.result(id2);

    REQUIRE(result1.has_value());
    REQUIRE(result1.value() == "55");

    REQUIRE(result2.has_value());

    REQUIRE(result2.value() == "25");

    REQUIRE(!manager.error(id1).has_value());
    REQUIRE(!manager.error(id2).has_value());

    bool resultExceptionThrown = false;

    try
    {
        manager.result(999);
    }
    catch (const std::out_of_range&)
    {
        resultExceptionThrown = true;
    }

    REQUIRE(resultExceptionThrown);

    REQUIRE(manager.status(id1) == JobStatus::Completed);
    REQUIRE(manager.status(id2) == JobStatus::Completed);

    bool exceptionThrown = false;

    try
    {
        manager.status(999);
    }
    catch (const std::out_of_range&)
    {
        exceptionThrown = true;
    }

    REQUIRE(exceptionThrown);


    {
        JobManager manager(1);

        manager.start();

        const auto id = manager.submit(
            JobType::Sleep,
            JobPriority::Normal,
            100
        );

        REQUIRE(manager.cancel(id));
        REQUIRE(manager.status(id) == JobStatus::Cancelled);

        REQUIRE(!manager.cancel(999));
    }


    {
        JobManager manager(1);

        manager.start();

        const auto id = manager.submit(
            JobType::Sleep,
            JobPriority::Normal,
            500
        );

        bool runningObserved = false;

        for (int i = 0; i < 100; ++i)
        {
            if (manager.status(id) == JobStatus::Running)
            {
                runningObserved = true;
                break;
            }

            std::this_thread::sleep_for(
                std::chrono::milliseconds(5)
            );
        }

        REQUIRE(runningObserved);

        const bool cancelled = manager.cancel(id);

        REQUIRE(cancelled);

        manager.stop();

        REQUIRE(manager.status(id) == JobStatus::Cancelled);
    }


    {
        JobManager manager(1);

        manager.start();

        const auto id = manager.submit(
            JobType::Sleep,
            JobPriority::Normal,
            500,
            std::chrono::milliseconds(50)
        );

        manager.stop();

        REQUIRE(manager.status(id) == JobStatus::TimedOut);
        REQUIRE(!manager.result(id).has_value());
    }

    {
        JobManager manager(1);

        manager.start();
        manager.stop();

        bool exceptionThrown = false;

        try
        {
            manager.submit(
                JobType::Sleep,
                JobPriority::Normal,
                100
            );
        }
        catch (const std::runtime_error&)
        {
            exceptionThrown = true;
        }

        REQUIRE(exceptionThrown);
    }

    {
        JobManager manager(1);

        manager.start();

        const auto id1 = manager.submit(
            JobType::Sleep,
            JobPriority::Normal,
            50
        );

        const auto id2 = manager.submit(
            JobType::Sleep,
            JobPriority::Normal,
            50
        );

        manager.stop();

        REQUIRE(manager.status(id1) == JobStatus::Completed);
        REQUIRE(manager.status(id2) == JobStatus::Completed);
    }

    {
        JobManager manager(4);

        manager.start();

        constexpr int threadCount = 4;
        constexpr int jobsPerThread = 200;
        constexpr int totalJobs = threadCount * jobsPerThread;

        std::vector<Job::Id> ids;
        ids.reserve(totalJobs);

        std::mutex idsMutex;

        std::vector<std::thread> threads;

        for (int i = 0; i < threadCount; ++i)
        {
            threads.emplace_back(
                [&]()
                {
                    for (int j = 0; j < jobsPerThread; ++j)
                    {
                        const auto id = manager.submit(
                            JobType::CalculateSum,
                            JobPriority::Normal,
                            10
                        );

                        std::lock_guard<std::mutex> lock(idsMutex);
                        ids.push_back(id);
                    }
                }
            );
        }

        for (auto& thread : threads)
        {
            thread.join();
        }

        REQUIRE(ids.size() == totalJobs);

        std::sort(ids.begin(), ids.end());

        for (int i = 0; i < totalJobs; ++i)
        {
            REQUIRE(ids[i] == static_cast<Job::Id>(i + 1));
        }
    }

    {
        JobManager manager(1);

        bool exceptionThrown = false;

        try
        {
            manager.submit(
                JobType::CalculateSum,
                JobPriority::Normal,
                10
            );
        }
        catch (const std::runtime_error&)
        {
            exceptionThrown = true;
        }

        REQUIRE(exceptionThrown);
    }
    return 0;
}