#include "job_system/job_manager.h"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sstream>
#include <chrono>

std::string statusToString(JobStatus status)
{
    switch (status)
    {
        case JobStatus::Queued:
            return "QUEUED";

        case JobStatus::Running:
            return "RUNNING";

        case JobStatus::Completed:
            return "COMPLETED";

        case JobStatus::Failed:
            return "FAILED";

        case JobStatus::Cancelled:
            return "CANCELLED";

        case JobStatus::TimedOut:
            return "TIMED_OUT";
    }

    return "UNKNOWN";
}

template <typename T>
bool readValue(const std::string& prompt, T& value)
{
    while (true)
    {
        std::cout << prompt;

        std::string line;

        if (!std::getline(std::cin, line))
        {
            return false;
        }

        std::istringstream input(line);

        if (input >> value)
        {
            input >> std::ws;

            if (input.eof())
            {
                return true;
            }
        }

        std::cout << "Invalid input. Try again.\n";
    }
}

int main()
{
    JobManager manager(4);
    manager.start();

    bool running = true;

    while (running)
    {
        std::cout << "\n=== JobProcessingSystem ===\n";
        std::cout << "1. Submit job\n";
        std::cout << "2. Check status\n";
        std::cout << "3. Get result\n";
        std::cout << "4. Cancel job\n";
        std::cout << "5. Statistics\n";
        std::cout << "6. Exit\n";

        int choice = 0;
        if (!readValue("Choice: ", choice))
        {
            std::cout << "\nInput closed. Shutting down...\n";
            break;
        }

        switch (choice)
        {
            case 1:
            {
                std::cout << "\nJob type:\n";
                std::cout << "1. CalculateSum\n";
                std::cout << "2. Sleep\n";
                std::cout << "3. CountPrimes\n";

                int typeChoice = 0;
                if (!readValue("Choice: ", typeChoice))
                {
                    running = false;
                    break;
                }

                JobType type;

                if (typeChoice == 1)
                {
                    type = JobType::CalculateSum;
                }
                else if (typeChoice == 2)
                {
                    type = JobType::Sleep;
                }
                else if (typeChoice == 3)
                {
                    type = JobType::CountPrimes;
                }
                else
                {
                    std::cout << "Invalid job type\n";
                    break;
                }

                std::cout << "\nPriority:\n";
                std::cout << "1. Low\n";
                std::cout << "2. Normal\n";
                std::cout << "3. High\n";

                int priorityChoice = 0;
                if (!readValue("Choice: ", priorityChoice))
                {
                    running = false;
                    break;
                }

                JobPriority priority;

                if (priorityChoice == 1)
                {
                    priority = JobPriority::Low;
                }
                else if (priorityChoice == 2)
                {
                    priority = JobPriority::Normal;
                }
                else if (priorityChoice == 3)
                {
                    priority = JobPriority::High;
                }
                else
                {
                    std::cout << "Invalid priority\n";
                    break;
                }

                std::cout << "Input value: ";

                std::int64_t input = 0;
                if (!readValue("Input value: ", input))
                {
                    running = false;
                    break;
                }

                try
                {
                    const auto id = manager.submit(
                        type,
                        priority,
                        input,
                        std::chrono::seconds(30)
                    );

                    std::cout << "Job submitted. ID = "
                              << id << '\n';
                }
                catch (const std::exception& exception)
                {
                    std::cout << "Submit failed: "
                              << exception.what() << '\n';
                }

                break;
            }

            case 2:
            {
                std::cout << "Job ID: ";

                Job::Id id = 0;
                if (!readValue("Job ID: ", id))
                {
                    running = false;
                    break;
                }

                try
                {
                    const auto status = manager.status(id);

                    std::cout << "Status: "
                              << statusToString(status)
                              << '\n';
                }
                catch (const std::out_of_range&)
                {
                    std::cout << "Job not found\n";
                }

                break;
            }

            case 3:
            {
                std::cout << "Job ID: ";

                Job::Id id = 0;
                if (!readValue("Job ID: ", id))
                {
                    running = false;
                    break;
                }

                try
                {
                    const auto result = manager.result(id);
                    const auto error = manager.error(id);

                    if (result.has_value())
                    {
                        std::cout << "Result: "
                                  << result.value()
                                  << '\n';
                    }
                    else if (error.has_value())
                    {
                        std::cout << "Error: "
                                  << error.value()
                                  << '\n';
                    }
                    else
                    {
                        std::cout
                            << "Result is not available yet\n";
                    }
                }
                catch (const std::out_of_range&)
                {
                    std::cout << "Job not found\n";
                }

                break;
            }

            case 4:
            {
                std::cout << "Job ID: ";

                Job::Id id = 0;
                if (!readValue("Job ID: ", id))
                {
                    running = false;
                    break;
                }

                if (manager.cancel(id))
                {
                    std::cout
                        << "Cancellation requested\n";
                }
                else
                {
                    std::cout
                        << "Job cannot be cancelled or does not exist\n";
                }

                break;
            }

            case 5:
            {
                const auto& statistics = manager.statistics();

                std::cout << "\n=== Statistics ===\n";
                std::cout << "Completed: " << statistics.completed() << '\n';
                std::cout << "Failed: " << statistics.failed() << '\n';
                std::cout << "Cancelled: " << statistics.cancelled() << '\n';
                std::cout << "Timed out: " << statistics.timedOut() << '\n';
                std::cout << "Average wait time: "
                        << statistics.averageWaitTimeMs()
                        << " ms\n";
                std::cout << "Average execution time: "
                        << statistics.averageExecutionTimeMs()
                        << " ms\n";

                break;
            }
    
            case 6:
            {
                std::cout << "Shutting down...\n";

                running = false;
                break;
            }

            default:
            {
                std::cout << "Invalid choice\n";
                break;
            }
        }
    }

    manager.stop();

    std::cout << "JobProcessingSystem stopped\n";

    return 0;
}