#include "RuntimeEventCollector.h"

#include <charconv>
#include <cctype>
#include <cstdlib>
#include <utility>

namespace infernux
{

namespace
{
using Clock = std::chrono::steady_clock;

bool _parse_bool_string(const std::string &value, bool *out)
{
    std::string lowered;
    lowered.reserve(value.size());
    for (unsigned char ch : value) {
        lowered.push_back(static_cast<char>(std::tolower(ch)));
    }

    if (lowered == "true" || lowered == "1") {
        *out = true;
        return true;
    }
    if (lowered == "false" || lowered == "0") {
        *out = false;
        return true;
    }
    return false;
}

bool _parse_int64_string(const std::string &value, int64_t *out)
{
    const char *begin = value.data();
    const char *end = begin + value.size();
    int64_t parsed = 0;
    const auto result = std::from_chars(begin, end, parsed);
    if (result.ec == std::errc() && result.ptr == end) {
        *out = parsed;
        return true;
    }
    return false;
}

bool _parse_double_string(const std::string &value, double *out)
{
    char *parse_end = nullptr;
    const double parsed = std::strtod(value.c_str(), &parse_end);
    if (parse_end != nullptr && *parse_end == '\0') {
        *out = parsed;
        return true;
    }
    return false;
}

RuntimeEventValue _typed_value_from_string(const std::string &raw)
{
    bool bool_value = false;
    if (_parse_bool_string(raw, &bool_value)) {
        return bool_value;
    }

    int64_t int_value = 0;
    if (_parse_int64_string(raw, &int_value)) {
        return int_value;
    }

    double double_value = 0.0;
    if (_parse_double_string(raw, &double_value)) {
        return double_value;
    }

    return raw;
}

RuntimeEventPayload _typed_payload_from_strings(const std::unordered_map<std::string, std::string> &payload)
{
    RuntimeEventPayload typed;
    for (const auto &entry : payload) {
        typed.emplace(entry.first, _typed_value_from_string(entry.second));
    }
    return typed;
}

RuntimeEventPayload _make_play_mode_payload(const std::string &state)
{
    RuntimeEventPayload payload;
    payload.emplace("state", state);
    return payload;
}

RuntimeEventPayload _make_input_injected_payload(const std::string &action, bool active, float x, float y)
{
    RuntimeEventPayload payload;
    payload.emplace("action", action);
    payload.emplace("active", active);
    if (action == "move") {
        payload.emplace("x", static_cast<double>(x));
        payload.emplace("y", static_cast<double>(y));
    }
    return payload;
}
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
                                           std::optional<std::vector<uint64_t>> targetEntityIds,
                                           std::optional<std::vector<uint64_t>> agentIds)
{
    std::lock_guard<std::mutex> lock(m_mutex);
    m_filter.event_types = eventTypes ? std::optional<std::unordered_set<std::string>>(MakeStringSet(*eventTypes))
                                       : std::nullopt;
    m_filter.source_entity_ids = sourceEntityIds ? std::optional<std::unordered_set<uint64_t>>(MakeIdSet(*sourceEntityIds))
                                                 : std::nullopt;
    m_filter.target_entity_ids = targetEntityIds ? std::optional<std::unordered_set<uint64_t>>(MakeIdSet(*targetEntityIds))
                                                  : std::nullopt;
    m_filter.agent_ids = agentIds ? std::optional<std::unordered_set<uint64_t>>(MakeIdSet(*agentIds))
                                  : std::nullopt;
}

void RuntimeEventCollector::ClearEventFilter()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    m_filter.event_types = std::nullopt;
    m_filter.source_entity_ids = std::nullopt;
    m_filter.target_entity_ids = std::nullopt;
    m_filter.agent_ids = std::nullopt;
}

uint64_t RuntimeEventCollector::GetCurrentFrame() const
{
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_frame;
}

void RuntimeEventCollector::RecordEvent(const std::string &type, std::optional<uint64_t> sourceEntityId,
                                        std::optional<uint64_t> targetEntityId, const RuntimeEventPayload &payload,
                                        std::optional<uint64_t> agentId)
{
    RuntimeEventRecord record;
    record.frame = m_frame;
    record.timestamp = NowMs();
    record.sequence = m_sequence++;
    record.agent_id = agentId;
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

    if (m_filter.agent_ids.has_value()) {
        if (!record.agent_id.has_value() ||
            m_filter.agent_ids->find(*record.agent_id) == m_filter.agent_ids->end()) {
            return false;
        }
    }

    return true;
}

void RuntimeEventCollector::RecordPlayModeStart()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent("PlayModeStart", std::nullopt, std::nullopt, _make_play_mode_payload("playing"));
}

void RuntimeEventCollector::RecordPlayModeStop()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent("PlayModeStop", std::nullopt, std::nullopt, _make_play_mode_payload("stopped"));
}

void RuntimeEventCollector::RecordInputInjected(const std::string &action, bool active, float x, float y)
{
    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent("InputInjected", std::nullopt, std::nullopt, _make_input_injected_payload(action, active, x, y),
                std::optional<uint64_t>(0));
}

void RuntimeEventCollector::RecordContactEvent(const std::string &type, std::optional<uint64_t> sourceEntityId,
                                               std::optional<uint64_t> targetEntityId,
                                               const std::unordered_map<std::string, std::string> &payload)
{
    std::lock_guard<std::mutex> lock(m_mutex);
    RecordEvent(type, sourceEntityId, targetEntityId, _typed_payload_from_strings(payload));
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
