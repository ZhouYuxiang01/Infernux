#pragma once

#include <chrono>
#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <mutex>
#include <optional>
#include <string>
#include <variant>
#include <unordered_set>
#include <unordered_map>
#include <vector>

namespace infernux
{

using RuntimeEventValue = std::variant<int64_t, double, bool, std::string, std::array<double, 3>>;
using RuntimeEventPayload = std::unordered_map<std::string, RuntimeEventValue>;

struct RuntimeEventRecord
{
    uint64_t frame = 0;
    int64_t timestamp = 0;
    uint64_t sequence = 0;
    std::optional<uint64_t> agent_id;
    std::string type;
    std::optional<uint64_t> source_entity_id;
    std::optional<uint64_t> target_entity_id;
    RuntimeEventPayload payload;
};

struct RuntimeEventFilter
{
    std::optional<std::unordered_set<std::string>> event_types;
    std::optional<std::unordered_set<uint64_t>> source_entity_ids;
    std::optional<std::unordered_set<uint64_t>> target_entity_ids;
    std::optional<std::unordered_set<uint64_t>> agent_ids;

    [[nodiscard]] bool IsEnabled() const
    {
        return event_types.has_value() || source_entity_ids.has_value() || target_entity_ids.has_value() ||
               agent_ids.has_value();
    }
};

class RuntimeEventCollector
{
  public:
    static RuntimeEventCollector &Instance();

    void BeginFrame();
    void ClearEvents();
    void SetEventFilter(std::optional<std::vector<std::string>> eventTypes,
                        std::optional<std::vector<uint64_t>> sourceEntityIds,
                        std::optional<std::vector<uint64_t>> targetEntityIds,
                        std::optional<std::vector<uint64_t>> agentIds = std::nullopt);
    void ClearEventFilter();

    void RecordPlayModeStart();
    void RecordPlayModeStop();
    void RecordInputInjected(const std::string &action, bool active, float x = 0.0f, float y = 0.0f);
    void RecordContactEvent(const std::string &type, std::optional<uint64_t> sourceEntityId,
                            std::optional<uint64_t> targetEntityId,
                            const std::unordered_map<std::string, std::string> &payload = {});

    [[nodiscard]] std::vector<RuntimeEventRecord> GetRecentEvents(int64_t windowMs) const;
    [[nodiscard]] uint64_t GetCurrentFrame() const;

  private:
    RuntimeEventCollector() = default;

    static int64_t NowMs();
    void RecordEvent(const std::string &type, std::optional<uint64_t> sourceEntityId,
                     std::optional<uint64_t> targetEntityId, const RuntimeEventPayload &payload,
                     std::optional<uint64_t> agentId = std::optional<uint64_t>(0));
    [[nodiscard]] bool MatchesFilter(const RuntimeEventRecord &record) const;
    static std::unordered_set<std::string> MakeStringSet(const std::vector<std::string> &values);
    static std::unordered_set<uint64_t> MakeIdSet(const std::vector<uint64_t> &values);

    static constexpr size_t kMaxEvents = 1000;

    mutable std::mutex m_mutex;
    std::deque<RuntimeEventRecord> m_events;
    RuntimeEventFilter m_filter;
    uint64_t m_frame = 0;
    uint64_t m_sequence = 0;
};

} // namespace infernux
