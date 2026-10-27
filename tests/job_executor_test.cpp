#include "job_system/job_executor.h"

#include "test_utils.h"
#include <chrono>
#include <thread>

int main()
{
    JobExecutor executor;

    Job job(
        1,
        JobType::CalculateSum,
        JobPriority::Normal,
        10
    );

    executor.execute(job);

    REQUIRE(job.status() == JobStatus::Completed);
    REQUIRE(job.result().has_value());
    REQUIRE(job.result().value() == "55");
    REQUIRE(!job.error().has_value());

    Job invalidJob(
        2,
        JobType::CalculateSum,
        JobPriority::Normal,
        -5
    );

    executor.execute(invalidJob);

    REQUIRE(invalidJob.status() == JobStatus::Failed);
    REQUIRE(invalidJob.error().has_value());


    Job primesJob(
    3,
    JobType::CountPrimes,
    JobPriority::Normal,
    10
    );

    executor.execute(primesJob);

    REQUIRE(primesJob.status() == JobStatus::Completed);
    REQUIRE(primesJob.result().has_value());
    REQUIRE(primesJob.result().value() == "4");


    Job sleepJob(
    4,
    JobType::Sleep,
    JobPriority::Low,
    10
    );

    executor.execute(sleepJob);

    REQUIRE(sleepJob.status() == JobStatus::Completed);
    REQUIRE(sleepJob.result().has_value());
    REQUIRE(sleepJob.result().value() == "Sleep completed");



    Job completedJob(
    5,
    JobType::CalculateSum,
    JobPriority::Normal,
    5
    );

    executor.execute(completedJob);

    REQUIRE(completedJob.status() == JobStatus::Completed);
    REQUIRE(completedJob.result().has_value());
    REQUIRE(completedJob.result().value() == "15");


    executor.execute(completedJob);

    REQUIRE(completedJob.status() == JobStatus::Completed);
    REQUIRE(completedJob.result().value() == "15");

    Job invalidSleepJob(
    6,
    JobType::Sleep,
    JobPriority::Low,
    -10
    );

    executor.execute(invalidSleepJob);

    REQUIRE(invalidSleepJob.status() == JobStatus::Failed);
    REQUIRE(invalidSleepJob.error().has_value());

    Job invalidPrimesJob(
    7,
    JobType::CountPrimes,
    JobPriority::Normal,
    -5
    );

    executor.execute(invalidPrimesJob);

    REQUIRE(invalidPrimesJob.status() == JobStatus::Failed);
    REQUIRE(invalidPrimesJob.error().has_value());

    return 0;
}