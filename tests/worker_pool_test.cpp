#include "job_system/worker_pool.h"

#include "test_utils.h"
#include <chrono>
#include <stdexcept>
#include <memory>
#include <thread>

int main()
{
    WorkerPool pool(4);

    pool.start();

    const auto start =
        std::chrono::steady_clock::now();

    for (Job::Id id = 1; id <= 4; ++id)
    {
        pool.submit(
            std::make_shared<Job>(
                id,
                JobType::Sleep,
                JobPriority::Normal,
                200
            )
        );
    }

    pool.stop();

    const auto end =
        std::chrono::steady_clock::now();

    const auto duration =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            end - start
        );

    REQUIRE(duration.count() < 600);


    bool exceptionThrown = false;

    try
    {
        WorkerPool invalidPool(0);
    }
    catch (const std::invalid_argument&)
    {
        exceptionThrown = true;
    }

    REQUIRE(exceptionThrown);
    
    {
        WorkerPool pool(2);

        pool.start();

        pool.submit(
            std::make_shared<Job>(
                100,
                JobType::Sleep,
                JobPriority::Normal,
                100
            )
        );

        pool.submit(
            std::make_shared<Job>(
                100,
                JobType::Sleep,
                JobPriority::Normal,
                100
            )
        );

    }

    {
        WorkerPool pool(2);


    }

    {
        WorkerPool pool(4);

        pool.start();

        std::this_thread::sleep_for(
            std::chrono::milliseconds(50)
        );

        const auto start =
            std::chrono::steady_clock::now();

        pool.stop();

        const auto end =
            std::chrono::steady_clock::now();

        const auto elapsed =
            std::chrono::duration_cast<std::chrono::milliseconds>(
                end - start
            );

        REQUIRE(elapsed.count() < 1000);
    }

    {
        WorkerPool pool(1);

        pool.start();

        bool exceptionThrown = false;

        try
        {
            pool.start();
        }
        catch (const std::logic_error&)
        {
            exceptionThrown = true;
        }

        REQUIRE(exceptionThrown);

        pool.stop();
    }

    {
        WorkerPool pool(1);

        pool.start();
        pool.stop();

        bool exceptionThrown = false;

        try
        {
            pool.start();
        }
        catch (const std::logic_error&)
        {
            exceptionThrown = true;
        }

        REQUIRE(exceptionThrown);
    }

    {
        WorkerPool pool(1);

        bool exceptionThrown = false;

        try
        {
            pool.submit(nullptr);
        }
        catch (const std::invalid_argument&)
        {
            exceptionThrown = true;
        }

        REQUIRE(exceptionThrown);
    }
    return 0;
}