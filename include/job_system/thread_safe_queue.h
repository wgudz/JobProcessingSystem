#pragma once

#include <condition_variable>
#include <mutex>
#include <queue>
#include <utility>
#include <optional>
#include <functional>

template <typename T>
class ThreadSafeQueue
{
public:
    explicit ThreadSafeQueue(
        std::function<int(const T&)> getPriority = nullptr,
        std::size_t maxSize = 1000
    );

    bool push(T value);
    std::optional<T> waitAndPop();
    void close();
    bool empty() const;
    

private:
    std::queue<T> highQueue_;
    std::queue<T> normalQueue_;
    std::queue<T> lowQueue_;

    mutable std::mutex mutex_;
    std::condition_variable condition_;
    bool closed_ = false;

    std::function<int(const T&)> getPriority_;

    std::size_t maxSize_;
};


template <typename T>
ThreadSafeQueue<T>::ThreadSafeQueue(
    std::function<int(const T&)> getPriority,
    std::size_t maxSize
)
    : getPriority_(std::move(getPriority)),
      maxSize_(maxSize)
{
}

template <typename T>
bool ThreadSafeQueue<T>::empty() const
{
    std::lock_guard<std::mutex> lock(mutex_);

    return highQueue_.empty()
        && normalQueue_.empty()
        && lowQueue_.empty();
}

template <typename T>
bool ThreadSafeQueue<T>::push(T value)
{
    {
        std::lock_guard<std::mutex> lock(mutex_);

        const auto currentSize =
            highQueue_.size() +
            normalQueue_.size() +
            lowQueue_.size();

        if (currentSize >= maxSize_)
        {
            return false;
        }

        if (closed_)
        {
            return false;
        }

        int priority = 1;

        if (getPriority_)
        {
            priority = getPriority_(value);
        }

        if (priority == 2)
        {
            highQueue_.push(std::move(value));
        }
        else if (priority == 0)
        {
            lowQueue_.push(std::move(value));
        }
        else
        {
            normalQueue_.push(std::move(value));
        }
    }

    condition_.notify_one();
    return true;
}

template <typename T>
std::optional<T> ThreadSafeQueue<T>::waitAndPop()
{
    std::unique_lock<std::mutex> lock(mutex_);

    condition_.wait(
        lock,
        [this]()
        {
            return closed_
                || !highQueue_.empty()
                || !normalQueue_.empty()
                || !lowQueue_.empty();
        }
    );

    if (highQueue_.empty()
        && normalQueue_.empty()
        && lowQueue_.empty())
    {
        return std::nullopt;
    }

    T value;

    if (!highQueue_.empty())
    {
        value = std::move(highQueue_.front());
        highQueue_.pop();
    }
    else if (!normalQueue_.empty())
    {
        value = std::move(normalQueue_.front());
        normalQueue_.pop();
    }
    else
    {
        value = std::move(lowQueue_.front());
        lowQueue_.pop();
    }

    return value;
}

template <typename T>
void ThreadSafeQueue<T>::close()
{
    {
        std::lock_guard<std::mutex> lock(mutex_);
        closed_ = true;
    }

    condition_.notify_all();
}