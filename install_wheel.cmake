if(NOT DEFINED INFERNUX_SOURCE_DIR OR INFERNUX_SOURCE_DIR STREQUAL "")
    message(FATAL_ERROR "INFERNUX_SOURCE_DIR is required")
endif()

if(NOT DEFINED PYTHON_EXECUTABLE OR PYTHON_EXECUTABLE STREQUAL "")
    message(FATAL_ERROR "PYTHON_EXECUTABLE is required")
endif()

# ── Detect editable install ──────────────────────────────────────────────
# When `pip install -e .` is active the .pyd is already copied by the
# POST_BUILD step, so there is nothing to install.  Overwriting with a
# wheel would destroy the editable link.
execute_process(
    COMMAND "${PYTHON_EXECUTABLE}" -c
        "import importlib.metadata, pathlib, sys; d = importlib.metadata.distribution('Infernux'); direct_url = d.read_text('direct_url.json'); editable = direct_url is not None and '\"editable\": true' in direct_url; sys.exit(0 if editable else 1)"
    RESULT_VARIABLE _editable_check
    OUTPUT_QUIET
    ERROR_QUIET
)

if(_editable_check EQUAL 0)
    message(STATUS "Infernux is installed as editable — skipping wheel install (the .pyd was already copied by POST_BUILD)")
    return()
endif()

# ── Regular wheel install ────────────────────────────────────────────────
file(GLOB WHEELS "${INFERNUX_SOURCE_DIR}/dist/*.whl")

list(LENGTH WHEELS WHEEL_COUNT)
if(WHEEL_COUNT EQUAL 0)
    message(FATAL_ERROR "No wheel found in ${INFERNUX_SOURCE_DIR}/dist")
endif()

list(GET WHEELS 0 FIRST_WHEEL)
execute_process(
    COMMAND "${PYTHON_EXECUTABLE}" -m pip uninstall -y Infernux
    RESULT_VARIABLE _pip_uninstall_result
    COMMAND_ECHO STDOUT
)

if(NOT _pip_uninstall_result EQUAL 0)
    message(FATAL_ERROR "Failed to uninstall existing Infernux package")
endif()

execute_process(
    COMMAND "${PYTHON_EXECUTABLE}" -m pip install --no-deps "${FIRST_WHEEL}"
    RESULT_VARIABLE _pip_install_result
    COMMAND_ECHO STDOUT
)

if(NOT _pip_install_result EQUAL 0)
    message(FATAL_ERROR "Failed to install wheel: ${FIRST_WHEEL}")
endif()
