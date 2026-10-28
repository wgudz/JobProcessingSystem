#include "job_system/job_manager.h"

#include "test_utils.h"
#include <chrono>
#include <thread>

int main()
{
    //anulowanie przed uruchomieniem
    {
        JobManager manager(1);

        manager.start();

        const auto id = manager.submit(
            JobType::Sleep,
            JobPriority::Normal,
            500
        );

        REQUIRE(manager.cancel(id));
        REQUIRE(manager.status(id) == JobStatus::Cancelled);
    }

    //anulowanie podczas wykonywania
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
        REQUIRE(manager.cancel(id));

        manager.stop();

        REQUIRE(manager.status(id) == JobStatus::Cancelled);
    }

    //timeout
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

    return 0;
}