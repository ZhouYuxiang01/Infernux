/**
 * @file AsyncTransferContext.cpp
 * @brief Implementation of the pooled async-upload pipeline.
 */

#include "AsyncTransferContext.h"
#include "VkDeviceContext.h"
#include <core/log/InxLog.h>

namespace infernux
{
namespace vk
{

namespace
{

constexpr uint64_t kPollTimeoutNs = 50'000'000; // 50 ms

void WaitFence(VkDevice device, VkFence fence)
{
    while (true) {
        VkResult result = vkWaitForFences(device, 1, &fence, VK_TRUE, kPollTimeoutNs);
        if (result == VK_SUCCESS) {
            return;
        }
        if (result != VK_TIMEOUT) {
            INXLOG_ERROR("AsyncTransferContext::WaitFence vkWaitForFences failed: ", VkResultToString(result));
            return;
        }
        // Pumping events here is intentionally omitted — async transfer
        // rarely takes anywhere near 50 ms; if it does, the OS already has
        // the main thread's loop pumping events on its own cadence.
    }
}

} // namespace

AsyncTransferContext::~AsyncTransferContext()
{
    Destroy();
}

bool AsyncTransferContext::Initialize(VkDevice device, uint32_t transferQueueFamily, VkQueue transferQueue,
                                      bool hasDedicatedTransferQueue)
{
    if (device == VK_NULL_HANDLE || transferQueue == VK_NULL_HANDLE) {
        INXLOG_ERROR("AsyncTransferContext::Initialize: null device or queue");
        return false;
    }

    m_device = device;
    m_queue = transferQueue;
    m_queueFamily = transferQueueFamily;
    m_hasDedicatedQueue = hasDedicatedTransferQueue;

    // Pool flags:
    //   - TRANSIENT_BIT: hint that command buffers are short-lived (driver
    //     can choose a faster allocation strategy)
    //   - RESET_COMMAND_BUFFER_BIT: required for vkResetCommandBuffer in
    //     the recycling path (otherwise we'd have to reset the entire pool
    //     on every reuse)
    VkCommandPoolCreateInfo poolInfo{};
    poolInfo.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    poolInfo.flags = VK_COMMAND_POOL_CREATE_TRANSIENT_BIT | VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    poolInfo.queueFamilyIndex = transferQueueFamily;

    if (vkCreateCommandPool(device, &poolInfo, nullptr, &m_pool) != VK_SUCCESS) {
        INXLOG_ERROR("AsyncTransferContext::Initialize: vkCreateCommandPool failed (family ", transferQueueFamily, ")");
        m_device = VK_NULL_HANDLE;
        return false;
    }

    INXLOG_INFO("AsyncTransferContext initialized on queue family ", transferQueueFamily,
                hasDedicatedTransferQueue ? " (dedicated DMA queue)" : " (aliased to graphics queue)");
    return true;
}

void AsyncTransferContext::Destroy() noexcept
{
    if (m_device == VK_NULL_HANDLE) {
        return;
    }

    // Anything still in flight at teardown is a logic bug, but be defensive:
    // wait on each in-flight fence so we don't try to destroy a fence the
    // GPU is still signalling.
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        for (const auto &up : m_inFlight) {
            if (up.fence != VK_NULL_HANDLE) {
                WaitFence(m_device, up.fence);
            }
        }
        m_inFlight.clear();

        for (VkFence fence : m_allFences) {
            if (fence != VK_NULL_HANDLE) {
                vkDestroyFence(m_device, fence, nullptr);
            }
        }
        m_allFences.clear();
        m_freeFences.clear();

        // Command buffers are owned by the pool; destroying the pool below
        // frees them implicitly.
        m_allCmdBuffers.clear();
        m_freeCmdBuffers.clear();
    }

    if (m_pool != VK_NULL_HANDLE) {
        vkDestroyCommandPool(m_device, m_pool, nullptr);
        m_pool = VK_NULL_HANDLE;
    }

    m_device = VK_NULL_HANDLE;
    m_queue = VK_NULL_HANDLE;
    m_queueFamily = 0;
    m_hasDedicatedQueue = false;
}

VkCommandBuffer AsyncTransferContext::AcquireCommandBufferLocked()
{
    if (!m_freeCmdBuffers.empty()) {
        VkCommandBuffer cmd = m_freeCmdBuffers.back();
        m_freeCmdBuffers.pop_back();
        vkResetCommandBuffer(cmd, 0);
        return cmd;
    }

    VkCommandBuffer cmd = VK_NULL_HANDLE;
    VkCommandBufferAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    allocInfo.commandPool = m_pool;
    allocInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    allocInfo.commandBufferCount = 1;

    if (vkAllocateCommandBuffers(m_device, &allocInfo, &cmd) != VK_SUCCESS) {
        INXLOG_ERROR("AsyncTransferContext: vkAllocateCommandBuffers failed");
        return VK_NULL_HANDLE;
    }

    m_allCmdBuffers.push_back(cmd);
    return cmd;
}

VkFence AsyncTransferContext::AcquireFenceLocked()
{
    if (!m_freeFences.empty()) {
        VkFence fence = m_freeFences.back();
        m_freeFences.pop_back();
        vkResetFences(m_device, 1, &fence);
        return fence;
    }

    VkFence fence = VK_NULL_HANDLE;
    VkFenceCreateInfo fenceInfo{};
    fenceInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;

    if (vkCreateFence(m_device, &fenceInfo, nullptr, &fence) != VK_SUCCESS) {
        INXLOG_ERROR("AsyncTransferContext: vkCreateFence failed");
        return VK_NULL_HANDLE;
    }

    m_allFences.push_back(fence);
    return fence;
}

VkCommandBuffer AsyncTransferContext::Begin()
{
    if (m_device == VK_NULL_HANDLE) {
        INXLOG_ERROR("AsyncTransferContext::Begin called on uninitialised context");
        return VK_NULL_HANDLE;
    }

    VkCommandBuffer cmd = VK_NULL_HANDLE;
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        // Reap completed uploads opportunistically — most frames there will
        // be a handful of small uploads in flight, and reaping here keeps
        // the free-list warm without a dedicated background thread.
        ReapCompletedLocked();
        cmd = AcquireCommandBufferLocked();
    }

    if (cmd == VK_NULL_HANDLE) {
        return VK_NULL_HANDLE;
    }

    VkCommandBufferBeginInfo beginInfo{};
    beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    beginInfo.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;

    if (vkBeginCommandBuffer(cmd, &beginInfo) != VK_SUCCESS) {
        INXLOG_ERROR("AsyncTransferContext::Begin: vkBeginCommandBuffer failed");
        std::lock_guard<std::mutex> guard(m_mutex);
        m_freeCmdBuffers.push_back(cmd);
        return VK_NULL_HANDLE;
    }

    return cmd;
}

void AsyncTransferContext::EndSync(VkCommandBuffer cmd)
{
    if (cmd == VK_NULL_HANDLE) {
        return;
    }

    vkEndCommandBuffer(cmd);

    VkFence fence = VK_NULL_HANDLE;
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        fence = AcquireFenceLocked();
    }
    if (fence == VK_NULL_HANDLE) {
        return;
    }

    VkSubmitInfo submit{};
    submit.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit.commandBufferCount = 1;
    submit.pCommandBuffers = &cmd;

    vkQueueSubmit(m_queue, 1, &submit, fence);
    WaitFence(m_device, fence);

    std::lock_guard<std::mutex> guard(m_mutex);
    m_freeFences.push_back(fence);
    m_freeCmdBuffers.push_back(cmd);
}

AsyncUploadHandle AsyncTransferContext::EndAsync(VkCommandBuffer cmd)
{
    AsyncUploadHandle handle{};
    if (cmd == VK_NULL_HANDLE) {
        return handle;
    }

    vkEndCommandBuffer(cmd);

    VkFence fence = VK_NULL_HANDLE;
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        fence = AcquireFenceLocked();
    }
    if (fence == VK_NULL_HANDLE) {
        return handle;
    }

    VkSubmitInfo submit{};
    submit.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit.commandBufferCount = 1;
    submit.pCommandBuffers = &cmd;

    if (vkQueueSubmit(m_queue, 1, &submit, fence) != VK_SUCCESS) {
        INXLOG_ERROR("AsyncTransferContext::EndAsync: vkQueueSubmit failed");
        std::lock_guard<std::mutex> guard(m_mutex);
        m_freeFences.push_back(fence);
        m_freeCmdBuffers.push_back(cmd);
        return handle;
    }

    handle.id = m_nextId.fetch_add(1, std::memory_order_relaxed);

    std::lock_guard<std::mutex> guard(m_mutex);
    m_inFlight.push_back({handle.id, fence, cmd});
    return handle;
}

void AsyncTransferContext::ReapCompletedLocked()
{
    for (auto it = m_inFlight.begin(); it != m_inFlight.end();) {
        VkResult result = vkGetFenceStatus(m_device, it->fence);
        if (result == VK_SUCCESS) {
            m_freeFences.push_back(it->fence);
            m_freeCmdBuffers.push_back(it->cmd);
            it = m_inFlight.erase(it);
        } else {
            ++it;
        }
    }
}

void AsyncTransferContext::RetireLocked(uint64_t id, VkFence &fence, VkCommandBuffer &cmd)
{
    fence = VK_NULL_HANDLE;
    cmd = VK_NULL_HANDLE;
    for (auto it = m_inFlight.begin(); it != m_inFlight.end(); ++it) {
        if (it->id == id) {
            fence = it->fence;
            cmd = it->cmd;
            m_inFlight.erase(it);
            return;
        }
    }
}

bool AsyncTransferContext::IsComplete(AsyncUploadHandle handle)
{
    if (!handle.IsValid() || m_device == VK_NULL_HANDLE) {
        return true;
    }

    std::lock_guard<std::mutex> guard(m_mutex);
    for (const auto &up : m_inFlight) {
        if (up.id == handle.id) {
            VkResult result = vkGetFenceStatus(m_device, up.fence);
            if (result == VK_SUCCESS) {
                VkFence fence = VK_NULL_HANDLE;
                VkCommandBuffer cmd = VK_NULL_HANDLE;
                RetireLocked(handle.id, fence, cmd);
                if (fence != VK_NULL_HANDLE) {
                    m_freeFences.push_back(fence);
                }
                if (cmd != VK_NULL_HANDLE) {
                    m_freeCmdBuffers.push_back(cmd);
                }
                return true;
            }
            return false;
        }
    }
    // Not found → already reaped.
    return true;
}

void AsyncTransferContext::Wait(AsyncUploadHandle handle)
{
    if (!handle.IsValid() || m_device == VK_NULL_HANDLE) {
        return;
    }

    VkFence fence = VK_NULL_HANDLE;
    {
        std::lock_guard<std::mutex> guard(m_mutex);
        for (const auto &up : m_inFlight) {
            if (up.id == handle.id) {
                fence = up.fence;
                break;
            }
        }
    }

    if (fence == VK_NULL_HANDLE) {
        return; // Already retired.
    }

    WaitFence(m_device, fence);

    std::lock_guard<std::mutex> guard(m_mutex);
    VkFence retiredFence = VK_NULL_HANDLE;
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    RetireLocked(handle.id, retiredFence, cmd);
    if (retiredFence != VK_NULL_HANDLE) {
        m_freeFences.push_back(retiredFence);
    }
    if (cmd != VK_NULL_HANDLE) {
        m_freeCmdBuffers.push_back(cmd);
    }
}

} // namespace vk
} // namespace infernux
