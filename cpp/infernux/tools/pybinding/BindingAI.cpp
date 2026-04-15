#include <function/ai/RuntimeEventCollector.h>
#include <memory>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

namespace infernux
{

void RegisterAIRuntimeBindings(py::module_ &m)
{
    py::class_<RuntimeEventRecord>(m, "RuntimeEventRecord")
        .def(py::init<>())
        .def_readonly("frame", &RuntimeEventRecord::frame)
        .def_readonly("timestamp", &RuntimeEventRecord::timestamp)
        .def_readonly("sequence", &RuntimeEventRecord::sequence)
        .def_readonly("type", &RuntimeEventRecord::type)
        .def_readonly("source_entity_id", &RuntimeEventRecord::source_entity_id)
        .def_readonly("target_entity_id", &RuntimeEventRecord::target_entity_id)
        .def_readonly("payload", &RuntimeEventRecord::payload);

    py::class_<RuntimeEventCollector, std::unique_ptr<RuntimeEventCollector, py::nodelete>>(m, "RuntimeEventCollector")
        .def_static("instance", &RuntimeEventCollector::Instance, py::return_value_policy::reference,
                    "Get the singleton runtime event collector")
        .def("begin_frame", &RuntimeEventCollector::BeginFrame, "Advance to the next runtime frame")
        .def("clear_events", &RuntimeEventCollector::ClearEvents, "Clear buffered events")
        .def(
            "set_event_filter",
            [](RuntimeEventCollector &collector, py::object eventTypes, py::object sourceEntityIds,
               py::object targetEntityIds) {
                std::optional<std::vector<std::string>> types;
                std::optional<std::vector<uint64_t>> sources;
                std::optional<std::vector<uint64_t>> targets;

                if (!eventTypes.is_none()) {
                    types = eventTypes.cast<std::vector<std::string>>();
                }
                if (!sourceEntityIds.is_none()) {
                    sources = sourceEntityIds.cast<std::vector<uint64_t>>();
                }
                if (!targetEntityIds.is_none()) {
                    targets = targetEntityIds.cast<std::vector<uint64_t>>();
                }

                collector.SetEventFilter(types, sources, targets);
            },
            py::arg("event_types") = py::none(), py::arg("source_entity_ids") = py::none(),
            py::arg("target_entity_ids") = py::none(), "Set the event read filter")
        .def("clear_event_filter", &RuntimeEventCollector::ClearEventFilter, "Clear the event read filter")
        .def("get_recent_events",
             [](RuntimeEventCollector &collector, double window_ms) {
                 py::list events;
                 for (const auto &record : collector.GetRecentEvents(static_cast<int64_t>(window_ms))) {
                     py::dict payload;
                     for (const auto &entry : record.payload) {
                         payload[py::str(entry.first)] = py::str(entry.second);
                     }

                     py::dict event;
                     event["frame"] = record.frame;
                     event["timestamp"] = record.timestamp;
                     event["sequence"] = record.sequence;
                     event["type"] = record.type;
                     event["source_entity_id"] = record.source_entity_id ? py::cast(*record.source_entity_id) : py::none();
                     event["target_entity_id"] = record.target_entity_id ? py::cast(*record.target_entity_id) : py::none();
                     event["payload"] = std::move(payload);
                     events.append(std::move(event));
                 }
                 return events;
             },
             py::arg("window_ms"), "Return buffered events from the last N milliseconds")
        .def_property_readonly("current_frame", &RuntimeEventCollector::GetCurrentFrame,
                               "Current runtime frame index");
}

} // namespace infernux
