#include "SceneRenderTarget.h"
#include "InxVkCoreModular.h"
#include "vk/VkDeviceContext.h"
#include "vk/VkRenderUtils.h"
#include <array>
#include <backends/imgui_impl_vulkan.h>
#include <core/log/InxLog.h>
#include <cstring>
#include <vk_mem_alloc.h>

namespace infernux
{

namespace
{

inline void SafeDestroyVmaImage(VmaAllocator allocator, VkImage &image, VmaAllocation &alloc)
{
    if (image != VK_NULL_HANDLE) {
        vmaDestroyImage(allocator, image, alloc);
        image = VK_NULL_HANDLE;
        alloc = VK_NULL_HANDLE;
    }
}

} // anonymous namespace

SceneRenderTarget::SceneRenderTarget(InxVkCoreModular *vkCore) : m_vkCore(vkCore)
{
}

SceneRenderTarget::~SceneRenderTarget()
{
    Cleanup();
}

bool SceneRenderTarget::Initialize(uint32_t width, uint32_t height)
{
    if (width == 0 || height == 0) {
        INXLOG_ERROR("SceneRenderTarget: Invalid dimensions ", width, "x", height);
        return false;
    }

    m_width = width;
    m_height = height;

    try {
        CreateColorAttachment();
        CreateColorStagingBuffer();
        if (m_msaaSampleCount != VK_SAMPLE_COUNT_1_BIT) {
            CreateMsaaColorAttachment();
        }
        CreateDepthAttachment();
        CreateOutlineMaskAttachment();
        // NOTE: Framebuffer is no longer created here - RenderGraph creates its own
        CreateImGuiDescriptor();
        m_isInitialized = true;
        // INXLOG_INFO("SceneRenderTarget initialized: ", width, "x", height);
        return true;
    } catch (const std::exception &e) {
        INXLOG_ERROR("SceneRenderTarget initialization failed: ", e.what());
        CleanupResources();
        return false;
    }
}

void SceneRenderTarget::Resize(uint32_t width, uint32_t height)
{
    if (width == m_width && height == m_height) {
        return;
    }

    // Wait for device to be idle before recreating resources
    m_vkCore->GetDeviceContext().WaitIdle();

    CleanupResources();
    Initialize(width, height);
}

VkFormat SceneRenderTarget::GetDepthFormat() const
{
    if (m_vkCore) {
        return m_vkCore->GetDeviceContext().FindDepthFormat();
    }
    return VK_FORMAT_D32_SFLOAT;
}

void SceneRenderTarget::CreateColorAttachment()
{
    auto imageInfo = vkrender::MakeImageCreateInfo2D(m_width, m_height, VK_FORMAT_R16G16B16A16_SFLOAT,
                                                     VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_SAMPLED_BIT |
                                                         VK_IMAGE_USAGE_TRANSFER_DST_BIT |
                                                         VK_IMAGE_USAGE_TRANSFER_SRC_BIT);

    VmaAllocator allocator = m_vkCore->GetDeviceContext().GetVmaAllocator();
    VmaAllocationCreateInfo allocCreateInfo{};
    allocCreateInfo.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;

    VkResult result =
        vmaCreateImage(allocator, &imageInfo, &allocCreateInfo, &m_colorImage, &m_colorAllocation, nullptr);
    if (result != VK_SUCCESS) {
        throw std::runtime_error("Failed to create color image via VMA");
    }

    auto viewInfo =
        vkrender::MakeImageViewCreateInfo2D(m_colorImage, VK_FORMAT_R16G16B16A16_SFLOAT, VK_IMAGE_ASPECT_COLOR_BIT);
    if (vkCreateImageView(m_vkCore->GetDevice(), &viewInfo, nullptr, &m_colorImageView) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create color image view");
    }

    // Transition to shader read optimal initially
    VkCommandBuffer cmdBuf = m_vkCore->BeginSingleTimeCommands();
    auto barrier =
        vkrender::MakeImageBarrier(m_colorImage, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
                                   VK_IMAGE_ASPECT_COLOR_BIT, 0, VK_ACCESS_SHADER_READ_BIT);
    vkCmdPipelineBarrier(cmdBuf, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0, 0,
                         nullptr, 0, nullptr, 1, &barrier);
    m_vkCore->EndSingleTimeCommands(cmdBuf);
}

bool SceneRenderTarget::ReadbackColorPixels(std::vector<uint8_t> &outData)
{
    outData.clear();
    if (!m_isInitialized || m_colorImage == VK_NULL_HANDLE || m_colorStagingBuffer == VK_NULL_HANDLE) {
        INXLOG_ERROR("SceneRenderTarget::ReadbackColorPixels: not initialized");
        return false;
    }

    VkCommandBuffer cmdBuf = m_vkCore->BeginSingleTimeCommands();

    auto barrier =
        vkrender::MakeImageBarrier(m_colorImage, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
                                   VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, VK_IMAGE_ASPECT_COLOR_BIT,
                                   VK_ACCESS_SHADER_READ_BIT, VK_ACCESS_TRANSFER_READ_BIT);
    vkCmdPipelineBarrier(cmdBuf, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, nullptr,
                         0, nullptr, 1, &barrier);

    VkBufferImageCopy region{};
    region.bufferOffset = 0;
    region.bufferRowLength = 0;
    region.bufferImageHeight = 0;
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.mipLevel = 0;
    region.imageSubresource.baseArrayLayer = 0;
    region.imageSubresource.layerCount = 1;
    region.imageOffset = {0, 0, 0};
    region.imageExtent = {m_width, m_height, 1};

    vkCmdCopyImageToBuffer(cmdBuf, m_colorImage, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, m_colorStagingBuffer, 1,
                           &region);

    barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(cmdBuf, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0, 0, nullptr,
                         0, nullptr, 1, &barrier);

    m_vkCore->EndSingleTimeCommands(cmdBuf);

    VmaAllocator allocator = m_vkCore->GetDeviceContext().GetVmaAllocator();
    void *data = nullptr;
    if (vmaMapMemory(allocator, m_colorStagingAllocation, &data) != VK_SUCCESS) {
        INXLOG_ERROR("SceneRenderTarget::ReadbackColorPixels: failed to map staging memory");
        return false;
    }

    outData.resize(static_cast<size_t>(m_colorStagingSize));
    std::memcpy(outData.data(), data, static_cast<size_t>(m_colorStagingSize));
    vmaUnmapMemory(allocator, m_colorStagingAllocation);

    return true;
}

void SceneRenderTarget::CreateMsaaColorAttachment()
{
    const VkSampleCountFlagBits msaaSamples = m_msaaSampleCount;

    // TRANSFER_SRC_BIT needed for explicit MSAA resolve via vkCmdResolveImage
    // (cannot use TRANSIENT_ATTACHMENT_BIT with TRANSFER_SRC_BIT)
    auto imageInfo = vkrender::MakeImageCreateInfo2D(
        m_width, m_height, VK_FORMAT_R16G16B16A16_SFLOAT,
        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT, msaaSamples);

    VmaAllocator allocator = m_vkCore->GetDeviceContext().GetVmaAllocator();
    VmaAllocationCreateInfo allocCreateInfo{};
    allocCreateInfo.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;

    VkResult result =
        vmaCreateImage(allocator, &imageInfo, &allocCreateInfo, &m_msaaColorImage, &m_msaaColorAllocation, nullptr);
    if (result != VK_SUCCESS) {
        throw std::runtime_error("Failed to create MSAA color image via VMA");
    }

    auto viewInfo =
        vkrender::MakeImageViewCreateInfo2D(m_msaaColorImage, VK_FORMAT_R16G16B16A16_SFLOAT, VK_IMAGE_ASPECT_COLOR_BIT);
    if (vkCreateImageView(m_vkCore->GetDevice(), &viewInfo, nullptr, &m_msaaColorImageView) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create MSAA color image view");
    }

    // Keep the real image layout aligned with the render-graph's tracked initial
    // state for the imported MSAA backbuffer.
    VkCommandBuffer cmdBuf = m_vkCore->BeginSingleTimeCommands();
    auto barrier = vkrender::MakeImageBarrier(m_msaaColorImage, VK_IMAGE_LAYOUT_UNDEFINED,
                                              VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, VK_IMAGE_ASPECT_COLOR_BIT, 0,
                                              VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT);
    vkCmdPipelineBarrier(cmdBuf, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, 0, 0,
                         nullptr, 0, nullptr, 1, &barrier);
    m_vkCore->EndSingleTimeCommands(cmdBuf);
}

void SceneRenderTarget::CreateDepthAttachment()
{
    VkFormat depthFormat = m_vkCore->GetDeviceContext().FindDepthFormat();

    auto imageInfo = vkrender::MakeImageCreateInfo2D(m_width, m_height, depthFormat,
                                                     VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT, m_msaaSampleCount);

    VmaAllocator allocator = m_vkCore->GetDeviceContext().GetVmaAllocator();
    VmaAllocationCreateInfo allocCreateInfo{};
    allocCreateInfo.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;

    VkResult result =
        vmaCreateImage(allocator, &imageInfo, &allocCreateInfo, &m_depthImage, &m_depthAllocation, nullptr);
    if (result != VK_SUCCESS) {
        throw std::runtime_error("Failed to create depth image via VMA");
    }

    auto viewInfo = vkrender::MakeImageViewCreateInfo2D(m_depthImage, depthFormat, VK_IMAGE_ASPECT_DEPTH_BIT);
    if (vkCreateImageView(m_vkCore->GetDevice(), &viewInfo, nullptr, &m_depthImageView) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create depth image view");
    }

    // Transition depth image to depth-stencil attachment optimal
    VkImageAspectFlags depthAspect = VK_IMAGE_ASPECT_DEPTH_BIT;
    if (vk::VkDeviceContext::HasStencilComponent(depthFormat)) {
        depthAspect |= VK_IMAGE_ASPECT_STENCIL_BIT;
    }

    VkCommandBuffer cmdBuf = m_vkCore->BeginSingleTimeCommands();
    auto barrier = vkrender::MakeImageBarrier(m_depthImage, VK_IMAGE_LAYOUT_UNDEFINED,
                                              VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL, depthAspect, 0,
                                              VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT);
    vkCmdPipelineBarrier(cmdBuf, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT, 0, 0,
                         nullptr, 0, nullptr, 1, &barrier);
    m_vkCore->EndSingleTimeCommands(cmdBuf);
}

void SceneRenderTarget::CreateImGuiDescriptor()
{
    auto samplerInfo = vkrender::MakeLinearClampSamplerInfo();
    if (vkCreateSampler(m_vkCore->GetDevice(), &samplerInfo, nullptr, &m_sampler) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create scene texture sampler");
    }

    // Create ImGui descriptor set for the texture
    m_imguiDescriptorSet =
        ImGui_ImplVulkan_AddTexture(m_sampler, m_colorImageView, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);

    if (m_imguiDescriptorSet == VK_NULL_HANDLE) {
        throw std::runtime_error("Failed to create ImGui descriptor set for scene texture");
    }
}

void SceneRenderTarget::CreateColorStagingBuffer()
{
    m_colorStagingSize = static_cast<VkDeviceSize>(m_width) * static_cast<VkDeviceSize>(m_height) * 8;

    VkBufferCreateInfo bufferInfo{};
    bufferInfo.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bufferInfo.size = m_colorStagingSize;
    bufferInfo.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT;
    bufferInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    VmaAllocator allocator = m_vkCore->GetDeviceContext().GetVmaAllocator();
    VmaAllocationCreateInfo allocCreateInfo{};
    allocCreateInfo.usage = VMA_MEMORY_USAGE_AUTO;
    allocCreateInfo.flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT;
    allocCreateInfo.requiredFlags = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;

    VkResult result =
        vmaCreateBuffer(allocator, &bufferInfo, &allocCreateInfo, &m_colorStagingBuffer, &m_colorStagingAllocation,
                        nullptr);
    if (result != VK_SUCCESS) {
        throw std::runtime_error("Failed to create scene render target staging buffer via VMA");
    }
}

void SceneRenderTarget::CreateOutlineMaskAttachment()
{
    VkDevice device = m_vkCore->GetDevice();

    auto imageInfo = vkrender::MakeImageCreateInfo2D(m_width, m_height, VK_FORMAT_R8G8B8A8_UNORM,
                                                     VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_SAMPLED_BIT);

    VmaAllocator allocator = m_vkCore->GetDeviceContext().GetVmaAllocator();
    VmaAllocationCreateInfo allocCreateInfo{};
    allocCreateInfo.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;

    vmaCreateImage(allocator, &imageInfo, &allocCreateInfo, &m_outlineMaskImage, &m_outlineMaskAllocation, nullptr);

    auto viewInfo =
        vkrender::MakeImageViewCreateInfo2D(m_outlineMaskImage, VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_ASPECT_COLOR_BIT);
    vkCreateImageView(device, &viewInfo, nullptr, &m_outlineMaskImageView);

    // Sampler for composite pass
    auto samplerInfo = vkrender::MakeLinearClampSamplerInfo(VK_BORDER_COLOR_FLOAT_OPAQUE_BLACK);
    vkCreateSampler(device, &samplerInfo, nullptr, &m_outlineMaskSampler);

    // Transition to shader-read initially (will be transitioned at runtime)
    VkCommandBuffer cmdBuf = m_vkCore->BeginSingleTimeCommands();
    auto barrier = vkrender::MakeImageBarrier(m_outlineMaskImage, VK_IMAGE_LAYOUT_UNDEFINED,
                                              VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, VK_IMAGE_ASPECT_COLOR_BIT, 0,
                                              VK_ACCESS_SHADER_READ_BIT);
    vkCmdPipelineBarrier(cmdBuf, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0, 0,
                         nullptr, 0, nullptr, 1, &barrier);
    m_vkCore->EndSingleTimeCommands(cmdBuf);
}

void SceneRenderTarget::CleanupResources()
{
    VkDevice device = m_vkCore->GetDevice();
    VmaAllocator allocator = m_vkCore->GetDeviceContext().GetVmaAllocator();

    if (m_imguiDescriptorSet != VK_NULL_HANDLE) {
        ImGui_ImplVulkan_RemoveTexture(m_imguiDescriptorSet);
        m_imguiDescriptorSet = VK_NULL_HANDLE;
    }

    if (m_colorStagingBuffer != VK_NULL_HANDLE) {
        vmaDestroyBuffer(allocator, m_colorStagingBuffer, m_colorStagingAllocation);
        m_colorStagingBuffer = VK_NULL_HANDLE;
        m_colorStagingAllocation = VK_NULL_HANDLE;
        m_colorStagingSize = 0;
    }

    vkrender::SafeDestroy(device, m_sampler);
    vkrender::SafeDestroy(device, m_outlineMaskSampler);
    vkrender::SafeDestroy(device, m_outlineMaskImageView);
    SafeDestroyVmaImage(allocator, m_outlineMaskImage, m_outlineMaskAllocation);
    vkrender::SafeDestroy(device, m_msaaColorImageView);
    SafeDestroyVmaImage(allocator, m_msaaColorImage, m_msaaColorAllocation);
    vkrender::SafeDestroy(device, m_depthImageView);
    SafeDestroyVmaImage(allocator, m_depthImage, m_depthAllocation);
    vkrender::SafeDestroy(device, m_colorImageView);
    SafeDestroyVmaImage(allocator, m_colorImage, m_colorAllocation);

    m_isInitialized = false;
}

void SceneRenderTarget::Cleanup()
{
    if (m_vkCore && m_vkCore->GetDevice() != VK_NULL_HANDLE) {
        if (!m_vkCore->IsShuttingDown()) {
            m_vkCore->GetDeviceContext().WaitIdle();
        }
        CleanupResources();
    }
}

} // namespace infernux
