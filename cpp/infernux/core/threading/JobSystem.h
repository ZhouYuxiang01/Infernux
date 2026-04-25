/**
 * @file JobSystem.h
 * @brief Engine-wide C++ thread pool for parallel work dispatch.
 *
 * Designed to live alongside Jolt's JobSystemThreadPool (used by physics)
 * and Python's ThreadPoolExecutor (used by editor / asset workflows).
 * The C++ side previously had no general-purpose worker pool, which forced
 * every parallel-friendly path (texture decoding, mesh import, render
 * command recording, scene tick parallelisation) to either go single
 * threaded or build its own ad-hoc threading.
 *
 * Design goals:
 *
 *   * Trivial to use — `JobSystem::Get().Schedule([]{ ... });` is the
 *     entire API for one-off work; a returned JobHandle lets callers
 *     join when needed.
 *   * Move-only handles, no exceptions in the worker loop.
 *   * Configurable worker count; defaults to (hw_concurrency - 1) so
 *     the main render thread never has to compete with workers for a
 *     core. -1 keeps the CPU breathing room for the OS / driver.
 *   * Mutex-guarded queue today. The interface is deliberately minimal
 *     so we can swap the queue for a lock-free MPMC ring buffer later
 *     without touching call sites.
 *   * Designed to coexist with — not replace — Jolt's pool. Physics
 *     keeps its own pool; this one is for everything else.
 *
 * Non-goals (documented for future readers):
 *
 *   * Work stealing — keep the implementation small until we measure
 *     contention on the shared queue. Most expected workloads are
 *     coarse-grained (per-pass / per-asset) where a shared queue is
 *     fine.
 *   * Job dependencies / DAG — handled at call site for now via Wait().
 *     Add a dependency graph layer when render-graph parallel recording
 *     actually lands.
 *   * Fiber support — Vulkan command recording does not need it.
 */

#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>

namespace infernux
{

/**
 * @brief Opaque, move-only handle identifying a single scheduled job.
 *
 * Wait()-able through JobSystem. Multiple handles can share the same
 * underlying counter — useful for ParallelFor where we want to wait on
 * an entire batch.
 */
class JobHandle
{
  public:
    JobHandle() = default;
    explicit JobHandle(std::shared_ptr<std::atomic<int>> counter) : m_counter(std::move(counter))
    {
    }

    JobHandle(const JobHandle &) = default;
    JobHandle &operator=(const JobHandle &) = default;
    JobHandle(JobHandle &&) noexcept = default;
    JobHandle &operator=(JobHandle &&) noexcept = default;

    [[nodiscard]] bool IsValid() const noexcept
    {
        return static_cast<bool>(m_counter);
    }

    /// @brief Non-blocking poll. Returns true once all referenced jobs have completed.
    [[nodiscard]] bool IsComplete() const noexcept
    {
        return m_counter && m_counter->load(std::memory_order_acquire) == 0;
    }

  private:
    friend class JobSystem;
    std::shared_ptr<std::atomic<int>> m_counter;
};

/**
 * @brief Engine-wide worker thread pool singleton.
 *
 * Initialize() must be called once at engine startup; Shutdown() once at
 * engine teardown. Get() returns the singleton in between. The singleton
 * is intentionally NOT initialised lazily — silent worker startup during
 * arbitrary translation units' static init would race with the rest of
 * engine bring-up.
 */
class JobSystem
{
  public:
    using JobFn = std::function<void()>;

    /// @brief Bring up the global pool with @p workerCount worker threads.
    /// @p workerCount = 0 picks (hw_concurrency - 1) clamped to [1, 32].
    /// Calling Initialize twice is a logic error and asserts in debug.
    static void Initialize(uint32_t workerCount = 0);

    /// @brief Shut the global pool down. Pending jobs are drained first,
    /// then workers are joined. Safe to call multiple times.
    static void Shutdown();

    /// @brief Access the global pool. Initialize() must have been called.
    [[nodiscard]] static JobSystem &Get();

    /// @brief Has Initialize() been called and Shutdown() not yet called?
    [[nodiscard]] static bool IsAvailable() noexcept;

    JobSystem(const JobSystem &) = delete;
    JobSystem &operator=(const JobSystem &) = delete;
    JobSystem(JobSystem &&) = delete;
    JobSystem &operator=(JobSystem &&) = delete;

    /// @brief Schedule a single job. Returns a handle for joining later.
    /// The handle stays valid even after the job completes — IsComplete()
    /// just observes a zeroed counter.
    JobHandle Schedule(JobFn job);

    /// @brief Schedule @p count jobs that share a single counter, useful
    /// for ParallelFor-style fan-out where the caller wants one wait point.
    /// @p factory is invoked once per index (0..count-1) on the calling
    /// thread to produce each individual job — keeps the hot scheduling
    /// loop free of allocation when the factory is a stateless lambda.
    JobHandle ScheduleBatch(uint32_t count, std::function<JobFn(uint32_t index)> factory);

    /// @brief Convenience: parallel-for over [0, count). Equivalent to
    /// ScheduleBatch + Wait but expresses intent more clearly at call sites.
    void ParallelFor(uint32_t count, std::function<void(uint32_t index)> body);

    /// @brief Block the caller until all jobs referenced by @p handle complete.
    /// Returns immediately when the handle is invalid or already complete.
    /// While blocked, the caller participates as an opportunistic worker —
    /// this prevents priority inversion when the main thread joins on jobs
    /// scheduled by helper code.
    void Wait(const JobHandle &handle);

    /// @brief How many worker threads are running. 0 if Shutdown.
    [[nodiscard]] uint32_t GetWorkerCount() const noexcept
    {
        return static_cast<uint32_t>(m_workers.size());
    }

  private:
    JobSystem() = default;
    ~JobSystem();

    struct Task
    {
        JobFn fn;
        std::shared_ptr<std::atomic<int>> counter;
    };

    void WorkerLoop();
    bool TryRunOne(); // Returns true if a task was executed.

    std::vector<std::thread> m_workers;
    std::queue<Task> m_queue;
    std::mutex m_queueMutex;
    std::condition_variable m_queueCv;
    std::atomic<bool> m_running{false};
};

} // namespace infernux
