/**
 * @file JobSystem.cpp
 * @brief Implementation of the engine-wide C++ worker thread pool.
 */

#include "JobSystem.h"
#include <algorithm>
#include <cassert>
#include <core/log/InxLog.h>

namespace infernux
{

namespace
{

JobSystem *g_instance = nullptr;
std::mutex g_singletonMutex;

uint32_t ResolveWorkerCount(uint32_t requested) noexcept
{
    if (requested != 0) {
        return std::clamp<uint32_t>(requested, 1u, 32u);
    }
    const auto detected = std::thread::hardware_concurrency();
    if (detected <= 1) {
        // Single-core or hardware_concurrency() returned 0 (allowed by the
        // standard) → still spin up one worker so call sites have a thread
        // to dispatch to without having to special-case JobSystem absence.
        return 1u;
    }
    return std::clamp<uint32_t>(detected - 1, 1u, 32u);
}

} // namespace

void JobSystem::Initialize(uint32_t workerCount)
{
    std::lock_guard<std::mutex> guard(g_singletonMutex);
    assert(g_instance == nullptr && "JobSystem::Initialize called twice");
    if (g_instance != nullptr) {
        INXLOG_WARN("JobSystem::Initialize called twice — ignoring second call");
        return;
    }

    g_instance = new JobSystem();
    g_instance->m_running.store(true, std::memory_order_release);

    const uint32_t resolved = ResolveWorkerCount(workerCount);
    g_instance->m_workers.reserve(resolved);
    for (uint32_t i = 0; i < resolved; ++i) {
        g_instance->m_workers.emplace_back([] { JobSystem::Get().WorkerLoop(); });
    }

    INXLOG_INFO("JobSystem online with ", resolved,
                " worker thread(s) (hw_concurrency=", std::thread::hardware_concurrency(), ")");
}

void JobSystem::Shutdown()
{
    JobSystem *toDestroy = nullptr;
    {
        std::lock_guard<std::mutex> guard(g_singletonMutex);
        toDestroy = g_instance;
        g_instance = nullptr;
    }

    if (toDestroy == nullptr) {
        return;
    }

    toDestroy->m_running.store(false, std::memory_order_release);
    toDestroy->m_queueCv.notify_all();

    for (auto &t : toDestroy->m_workers) {
        if (t.joinable()) {
            t.join();
        }
    }
    toDestroy->m_workers.clear();

    delete toDestroy;
}

JobSystem &JobSystem::Get()
{
    // Fast path: no lock for the common case where Initialize already ran.
    // Initialize/Shutdown are coarse one-shot events so a relaxed read here
    // is fine; the assert protects against misuse from arbitrary call sites.
    assert(g_instance != nullptr && "JobSystem::Get called before Initialize");
    return *g_instance;
}

bool JobSystem::IsAvailable() noexcept
{
    std::lock_guard<std::mutex> guard(g_singletonMutex);
    return g_instance != nullptr;
}

JobSystem::~JobSystem()
{
    // Shutdown should already have joined workers; if not, do it defensively
    // so destruction never leaves a dangling thread.
    m_running.store(false, std::memory_order_release);
    m_queueCv.notify_all();
    for (auto &t : m_workers) {
        if (t.joinable()) {
            t.join();
        }
    }
}

JobHandle JobSystem::Schedule(JobFn job)
{
    auto counter = std::make_shared<std::atomic<int>>(1);
    Task task{std::move(job), counter};
    {
        std::lock_guard<std::mutex> guard(m_queueMutex);
        m_queue.push(std::move(task));
    }
    m_queueCv.notify_one();
    return JobHandle(std::move(counter));
}

JobHandle JobSystem::ScheduleBatch(uint32_t count, std::function<JobFn(uint32_t)> factory)
{
    if (count == 0) {
        return JobHandle();
    }

    auto counter = std::make_shared<std::atomic<int>>(static_cast<int>(count));
    {
        std::lock_guard<std::mutex> guard(m_queueMutex);
        for (uint32_t i = 0; i < count; ++i) {
            m_queue.push(Task{factory(i), counter});
        }
    }
    m_queueCv.notify_all();
    return JobHandle(std::move(counter));
}

void JobSystem::ParallelFor(uint32_t count, std::function<void(uint32_t)> body)
{
    if (count == 0) {
        return;
    }
    auto handle = ScheduleBatch(count, [body](uint32_t i) -> JobFn { return [body, i] { body(i); }; });
    Wait(handle);
}

void JobSystem::Wait(const JobHandle &handle)
{
    if (!handle.IsValid()) {
        return;
    }

    // Opportunistic helper-thread participation: instead of a passive
    // condition_variable wait, the joining thread runs queued tasks itself
    // until the counter zeroes out. This protects against priority inversion
    // when the main render thread joins on jobs scheduled by helpers.
    while (handle.m_counter->load(std::memory_order_acquire) > 0) {
        if (!TryRunOne()) {
            // Queue empty but our counter not yet zero → workers are still
            // executing the last task(s); just yield instead of busy-waiting.
            std::this_thread::yield();
        }
    }
}

bool JobSystem::TryRunOne()
{
    Task task;
    {
        std::lock_guard<std::mutex> guard(m_queueMutex);
        if (m_queue.empty()) {
            return false;
        }
        task = std::move(m_queue.front());
        m_queue.pop();
    }

    if (task.fn) {
        task.fn();
    }
    if (task.counter) {
        task.counter->fetch_sub(1, std::memory_order_acq_rel);
    }
    return true;
}

void JobSystem::WorkerLoop()
{
    while (m_running.load(std::memory_order_acquire)) {
        Task task;
        {
            std::unique_lock<std::mutex> guard(m_queueMutex);
            m_queueCv.wait(guard, [this] { return !m_queue.empty() || !m_running.load(std::memory_order_acquire); });

            if (!m_running.load(std::memory_order_acquire) && m_queue.empty()) {
                return;
            }

            if (m_queue.empty()) {
                continue;
            }

            task = std::move(m_queue.front());
            m_queue.pop();
        }

        if (task.fn) {
            // Errors in user-supplied jobs are bugs in the caller — let
            // them propagate so the worker thread terminates with a
            // diagnosable stack instead of silently dropping work.
            task.fn();
        }
        if (task.counter) {
            task.counter->fetch_sub(1, std::memory_order_acq_rel);
        }
    }
}

} // namespace infernux
