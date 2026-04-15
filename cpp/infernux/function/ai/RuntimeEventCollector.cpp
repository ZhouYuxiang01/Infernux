#include "RuntimeEventCollector.h"

#include <utility>

namespace infernux
{

namespace
{
using Clock = std::chrono::steady_clock;
}

RuntimeEventCollector &RuntimeEventCollector::Instance()
{
    static RuntimeEventCollector instance;
    return instance;
}

int64_t RuntimeEventCollector::NowMs()
{
    return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now().time_since_epoch()).count();
}

std::unordered_set<std::string> RuntimeEventCollector::MakeStringSet(const std::vector<std::string> &values)
{
    return std::unordered_set<std::string>(values.begin(), values.end());
}

std::unordered_set<uint64_t> RuntimeEventCollector::MakeIdSet(const std::vector<uint64_t> &values)
{
    return std::unordered_set<uint64_t>(values.begin(), values.end());
}

void RuntimeEventCollector::BeginFrame()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    ++m_frame;
    m_sequence = 0;
}

void RuntimeEventCollector::ClearEvents()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    m_events.clear();
}

void RuntimeEventCollector::SetEventFilter(std::optional<std::vector<std::string>> eventTypes,
                                           std::optional<std::vector<uint64_t>> sourceEntityIds,
                                           std::optional<std::vector<uint64_t>> targetEntityIds)
{
    std::lock_guard<std::mutex> lock(m_mutex);
    m_filter.event_types = eventTypes ? std::optional<std::unordered_set<std::string>>(MakeStringSet(*eventTypes))
                                       : std::nullopt;
    m_filter.source_entity_ids = sourceEntityIds ? std::optional<std::unordered_set<uint64_t>>(MakeIdSet(*sourceEntityIds))
                                                 : std::nullopt;
    m_filter.target_entity_ids = targetEntityIds ? std::optional<std::unordered_set<uint64_t>>(MakeIdSet(*targetEntityIds))
                                                  : std::nullopt;
}

void RuntimeEventCollector::ClearEventFilter()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    m_filter.event_types = std::nullopt;
    m_filter.source_entity_ids = std::nullopt;
    m_filter.target_entity_ids = std::nullopt;
}

uint64_t RuntimeEventCollector::GetCurrentFrame() const
{
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_frame;
}

void RuntimeEventCollector::RecordEvent(const std::string &type, std::optional<uint64_t> sourceEntityId,
                                        std::optional<uint64_t> targetEntityId,
                                        const std::unordered_map<std::string, std::string> &payload)
{
    RuntimeEventRecord record;
    record.frame = m_frame;
    record.timestamp = NowMs();
    record.sequence = m_sequence++;
    record.type = type;
    record.source_entity_id = sourceEntityId;
    record.target_entity_id = targetEntityId;
    record.payload = payload;

    m_events.push_back(std::move(record));
    while (m_events.size() > kMaxEvents) {
        m_events.pop_front();
    }
}

bool RuntimeEventCollector::MatchesFilter(const RuntimeEventRecord &record) const
{
    if (!m_filter.IsEnabled()) {
        return true;
    }

    if (m_filter.event_types.has_value() && m_filter.event_types->find(record.type) == m_filter.event_types->end()) {
        return false;
    }

    if (m_filter.source_entity_ids.has_value()) {
        if (!record.source_entity_id.has_value() ||
            m_filter.source_entity_ids->find(*record.source_entity_id) == m_filter.source_entity_ids->end()) {
            return false;
        }
    }

    if (m_filter.target_entity_ids.has_value()) {
        if (!record.target_entity_id.has_value() ||
            m_filter.target_entity_ids->find(*record.target_entity_id) == m_filter.target_entity_ids->end()) {
            return false;
        }
    }

    return true;
}

void RuntimeEventCollector::RecordPlayModeStart()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent("PlayModeStart", std::nullopt, std::nullopt, {{"state", "playing"}});
}

void RuntimeEventCollector::RecordPlayModeStop()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent("PlayModeStop", std::nullopt, std::nullopt, {{"state", "stopped"}});
}

void RuntimeEventCollector::RecordInputInjected(const std::string &action, bool active, float x, float y)
{
    std::unordered_map<std::string, std::string> payload;
    payload.emplace("action", action);
    payload.emplace("active", active ? "true" : "false");
    if (action == "move") {
        payload.emplace("x", std::to_string(x));
        payload.emplace("y", std::to_string(y));
    }

    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent("InputInjected", std::nullopt, std::nullopt, payload);
}

void RuntimeEventCollector::RecordContactEvent(const std::string &type, std::optional<uint64_t> sourceEntityId,
                                               std::optional<uint64_t> targetEntityId,
                                               const std::unordered_map<std::string, std::string> &payload)
{
    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent(type, sourceEntityId, targetEntityId, payload);
}

std::vector<RuntimeEventRecord> RuntimeEventCollector::GetRecentEvents(int64_t windowMs) const
{
    if (windowMs <= 0) {
        return {};
    }

    const int64_t cutoff = NowMs() - windowMs;
    std::lock_guard<std::mutex> lock(m_mutex);
    std::vector<RuntimeEventRecord> result;
    result.reserve(m_events.size());

    for (const auto &evt : m_events) {
        if (evt.timestamp >= cutoff && MatchesFilter(evt)) {
            result.push_back(evt);
        }
    }

    return result;
}

} // namespace infernux
