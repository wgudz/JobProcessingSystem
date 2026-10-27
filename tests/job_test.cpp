#include "job_system/job.h"

#include "test_utils.h"
#include <stdexcept>

int main()
{
    Job job(
        1,
        JobType::CalculateSum,
        JobPriority::High,
        100
    );

    REQUIRE(job.id() == 1);
    REQUIRE(job.type() == JobType::CalculateSum);
    REQUIRE(job.status() == JobStatus::Queued);
    REQUIRE(job.priority() == JobPriority::High);

    REQUIRE(job.setStatus(JobStatus::Running));
    REQUIRE(job.status() == JobStatus::Running);

    job.setResult("42");
    REQUIRE(job.result().has_value());
    REQUIRE(job.result().value() == "42");

    REQUIRE(job.setStatus(JobStatus::Completed));
    REQUIRE(job.status() == JobStatus::Completed);

    REQUIRE(!job.setStatus(JobStatus::Running));
    REQUIRE(job.status() == JobStatus::Completed);


    Job failedJob(
        2,
        JobType::CountPrimes,
        JobPriority::Normal,
        100
    );

    REQUIRE(failedJob.status() == JobStatus::Queued);

    REQUIRE(failedJob.setStatus(JobStatus::Running));
    REQUIRE(failedJob.status() == JobStatus::Running);

    failedJob.setError("Invalid input");

    REQUIRE(failedJob.error().has_value());
    REQUIRE(failedJob.error().value() == "Invalid input");

    REQUIRE(failedJob.setStatus(JobStatus::Failed));
    REQUIRE(failedJob.status() == JobStatus::Failed);

    REQUIRE(!failedJob.setStatus(JobStatus::Completed));
    REQUIRE(!failedJob.setStatus(JobStatus::Running));
    REQUIRE(failedJob.status() == JobStatus::Failed);



    bool exceptionThrown = false;

    try
    {
        Job invalidJob(
            0,
            JobType::Sleep,
            JobPriority::Low,
            100
        );
    }
    catch (const std::invalid_argument&)
    {
        exceptionThrown = true;
    }

    REQUIRE(exceptionThrown);

    {
        Job job(
            100,
            JobType::CalculateSum,
            JobPriority::Normal,
            10
        );

        REQUIRE(job.setStatus(JobStatus::Running));

        REQUIRE(
            job.requestCancel() ==
            CancelResult::CancellationRequested
        );

        const bool completed = job.complete("55");

        REQUIRE(!completed);
        REQUIRE(job.status() == JobStatus::Cancelled);
        REQUIRE(!job.result().has_value());
    }


    {
        Job job(
            101,
            JobType::CalculateSum,
            JobPriority::Normal,
            10
        );

        REQUIRE(job.setStatus(JobStatus::Running));

        REQUIRE(job.complete("55"));

        REQUIRE(job.status() == JobStatus::Completed);
        REQUIRE(job.result().value() == "55");

        REQUIRE(
            job.requestCancel() ==
            CancelResult::Rejected
        );
    }

    {
        Job job(
            102,
            JobType::CalculateSum,
            JobPriority::Normal,
            10
        );

        job.setTimeout(std::chrono::milliseconds(0));

        REQUIRE(job.setStatus(JobStatus::Running));

        const bool completed = job.complete("55");

        REQUIRE(!completed);
        REQUIRE(job.status() == JobStatus::TimedOut);
        REQUIRE(!job.result().has_value());
    }

    {
        Job job(
            103,
            JobType::CalculateSum,
            JobPriority::Normal,
            10
        );

        REQUIRE(job.setStatus(JobStatus::Running));

        REQUIRE(
            job.requestCancel() ==
            CancelResult::CancellationRequested
        );

        REQUIRE(!job.setStatus(JobStatus::Completed));

        REQUIRE(job.status() == JobStatus::Cancelled);
    }
    return 0;
}