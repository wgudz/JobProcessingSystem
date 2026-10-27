#include "job_system/statistics.h"

#include "test_utils.h"
#include <chrono>

int main()
{
    Statistics statistics;

    REQUIRE(statistics.completed() == 0);
    REQUIRE(statistics.failed() == 0);
    REQUIRE(statistics.cancelled() == 0);
    REQUIRE(statistics.timedOut() == 0);

    REQUIRE(statistics.averageWaitTimeMs() == 0.0);
    REQUIRE(statistics.averageExecutionTimeMs() == 0.0);

    statistics.recordCompleted(
        std::chrono::milliseconds(10),
        std::chrono::milliseconds(100)
    );

    statistics.recordFailed(
        std::chrono::milliseconds(20),
        std::chrono::milliseconds(200)
    );

    statistics.recordCancelled(
        std::chrono::milliseconds(30),
        std::chrono::milliseconds(300)
    );

    statistics.recordTimedOut(
        std::chrono::milliseconds(40),
        std::chrono::milliseconds(400)
    );

    REQUIRE(statistics.completed() == 1);
    REQUIRE(statistics.failed() == 1);
    REQUIRE(statistics.cancelled() == 1);
    REQUIRE(statistics.timedOut() == 1);

    REQUIRE(statistics.averageWaitTimeMs() == 25.0);
    REQUIRE(statistics.averageExecutionTimeMs() == 250.0);

    return 0;
}