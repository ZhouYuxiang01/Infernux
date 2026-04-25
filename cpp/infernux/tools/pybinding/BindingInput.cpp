/**
 * @file BindingInput.cpp
 * @brief Python bindings for InputManager — Unity-style input query API.
 *
 * Exposes the InputManager singleton so that the Python `Input` static class
 * can delegate to C++ for frame-accurate key/mouse/touch queries.
 *
 * Naming follows Unity conventions with Python snake_case:
 *   C++ GetKeyDown(scancode)  →  Python input_manager.get_key_down(scancode)
 */

#include <platform/input/InputManager.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

namespace infernux
{

void RegisterInputBindings(py::module_ &m)
{
    py::class_<InputChannel>(m, "InputChannel")
        .def(py::init<>())
        .def_readwrite("channel_id", &InputChannel::channel_id)
        .def_readwrite("axes", &InputChannel::axes)
        .def_readwrite("buttons", &InputChannel::buttons)
        .def_readwrite("duration_ms", &InputChannel::duration_ms)
        .def_readwrite("timestamp_ms", &InputChannel::timestamp_ms)
        .def_readwrite("agent_id", &InputChannel::agent_id);

    py::class_<VirtualInputState>(m, "VirtualInputState")
        .def(py::init<>())
        .def_readonly("jump", &VirtualInputState::jump)
        .def_readonly("attack", &VirtualInputState::attack)
        .def_readonly("move_x", &VirtualInputState::move_x)
        .def_readonly("move_y", &VirtualInputState::move_y);

    py::class_<InputManager, std::unique_ptr<InputManager, py::nodelete>>(
        m, "InputManager", "Low-level input state manager. Use the Python `Input` class for the public API.")

        .def_static("instance", &InputManager::Instance, py::return_value_policy::reference,
                    "Get the singleton InputManager instance")

        // ---- Keyboard ----
        .def("get_key", &InputManager::GetKey, py::arg("scancode"), "True while the key (by SDL scancode) is held down")
        .def("get_key_down", &InputManager::GetKeyDown, py::arg("scancode"),
             "True during the frame the key was pressed")
        .def("get_key_up", &InputManager::GetKeyUp, py::arg("scancode"), "True during the frame the key was released")
        .def("any_key", &InputManager::AnyKey, "True if any key is currently held down")
        .def("any_key_down", &InputManager::AnyKeyDown, "True during the frame any key was first pressed")

        // ---- Mouse buttons ----
        .def("get_mouse_button", &InputManager::GetMouseButton, py::arg("button"),
             "True while mouse button is held (0=left, 1=right, 2=middle)")
        .def("get_mouse_button_down", &InputManager::GetMouseButtonDown, py::arg("button"),
             "True during the frame the mouse button was pressed")
        .def("get_mouse_button_up", &InputManager::GetMouseButtonUp, py::arg("button"),
             "True during the frame the mouse button was released")
        .def("get_mouse_frame_state", &InputManager::GetMouseFrameState, py::arg("button"),
             "Return (mouse_x, mouse_y, scroll_x, scroll_y, held, down, up) for one mouse button")
        .def_property_readonly("virtual_input_state",
                               [](InputManager &mgr) -> const VirtualInputState & {
                                   return mgr.GetVirtualInputState();
                               },
                               py::return_value_policy::reference_internal,
                               "Current virtual input state used by action injection")
        .def("set_virtual_action", &InputManager::SetVirtualAction, py::arg("action"),
             py::arg("active") = true, py::arg("x") = 0.f, py::arg("y") = 0.f,
             "Set a virtual action state (jump / attack / move)")
        .def("clear_virtual_actions", &InputManager::ClearVirtualActions, "Clear all virtual actions")
        .def("submit_channel_signal", &InputManager::SubmitChannelSignal, py::arg("signal"),
             "Submit a generic input channel signal")
        .def("clear_channel", &InputManager::ClearChannel, py::arg("channel_id") = -1,
             "Clear a channel or all channels")
        .def("get_channel_state",
             [](InputManager &mgr, int channel_id) -> const InputChannel * { return mgr.GetChannelState(channel_id); },
             py::arg("channel_id") = 0, py::return_value_policy::reference_internal,
             "Return the last submitted channel state, if any")

        // ---- Mouse position & delta ----
        .def_property_readonly("mouse_position_x", &InputManager::GetMousePositionX,
                               "Current mouse X (window-space pixels)")
        .def_property_readonly("mouse_position_y", &InputManager::GetMousePositionY,
                               "Current mouse Y (window-space pixels)")
        .def_property_readonly("mouse_delta_x", &InputManager::GetMouseDeltaX, "Mouse X movement this frame")
        .def_property_readonly("mouse_delta_y", &InputManager::GetMouseDeltaY, "Mouse Y movement this frame")

        // ---- Scroll wheel ----
        .def_property_readonly("mouse_scroll_delta_y", &InputManager::GetMouseScrollDeltaY,
                               "Vertical scroll delta (positive = up)")
        .def_property_readonly("mouse_scroll_delta_x", &InputManager::GetMouseScrollDeltaX, "Horizontal scroll delta")

        // ---- Text input ----
        .def_property_readonly("input_string", &InputManager::GetInputString, "Characters typed this frame (UTF-8)")

        // ---- Touch ----
        .def_property_readonly("touch_count", &InputManager::GetTouchCount, "Number of active touch contacts")

        // ---- File drop (OS drag-drop) ----
        .def("has_dropped_files", &InputManager::HasDroppedFiles,
             "True if files were dropped onto the window this frame")
        .def("get_dropped_files", &InputManager::GetDroppedFiles, "List of file paths dropped this frame")

        // ---- Cursor lock ----
        .def("set_cursor_locked", &InputManager::SetCursorLocked, py::arg("locked"),
             "Lock/unlock cursor (hides cursor and captures relative mouse movement)")
        .def_property_readonly("is_cursor_locked", &InputManager::IsCursorLocked,
                               "True when cursor is locked (relative mouse mode)")
        .def("set_editor_mouse_capture", &InputManager::SetEditorMouseCapture, py::arg("captured"),
             "Enable or disable editor-only Scene view mouse capture without marking gameplay cursor lock")
        .def_property_readonly("is_editor_mouse_capture_active", &InputManager::IsEditorMouseCaptureActive,
                               "True when the Scene view editor camera is using relative mouse capture")

        // ---- Utility ----
        .def("reset_all", &InputManager::ResetAll, "Clear all input state (focus loss, scene change, etc.)")
        .def_static("name_to_scancode", &InputManager::NameToScancode, py::arg("name"),
                    "Map a key name (e.g. 'space', 'a', 'left shift') to SDL scancode. Returns -1 if unknown.")
        .def_static("scancode_to_name", &InputManager::ScancodeToName, py::arg("scancode"),
                    "Get the human-readable name for a scancode");
}

} // namespace infernux
