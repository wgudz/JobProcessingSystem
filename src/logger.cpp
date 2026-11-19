#include "job_system/logger.h"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <stdexcept>

Logger::Logger(std::ostream& output)
    : output_(output)
{
}

std::string Logger::levelToString(LogLevel level) const
{
    switch (level)
    {
        case LogLevel::Info:
            return "INFO";

        case LogLevel::Warning:
            return "WARNING";

        case LogLevel::Error:
            return "ERROR";
    }

    return "UNKNOWN";
}

void Logger::log(
    LogLevel level,
    std::size_t workerId,
    Job::Id jobId,
    const std::string& message
)
{
    const auto now = std::chrono::system_clock::now();
    const auto time = std::chrono::system_clock::to_time_t(now);

    std::tm localTime{};

    #ifdef _WIN32
        const bool time_ok =
            localtime_s(&localTime, &time) == 0;
    #else
        const bool time_ok =
            localtime_r(&time, &localTime) != nullptr;
    #endif

    if (!time_ok) {
        throw std::runtime_error(
            "Cannot convert current time"
        );
    }

    const auto milliseconds =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            now.time_since_epoch()
        ) % 1000;

    std::ostringstream line;

    line
        << std::put_time(&localTime, "%H:%M:%S")
        << '.'
        << std::setw(3)
        << std::setfill('0')
        << milliseconds.count()
        << ' '
        << levelToString(level)
        << " worker=" << workerId
        << " job=" << jobId
        << ' '
        << message;

    std::lock_guard<std::mutex> lock(mutex_);

    output_ << line.str() << '\n';
}