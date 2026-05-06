from __future__ import annotations

import importlib.util
import json

import pytest

from Infernux.engine.game_builder import BuildOutputDirectoryError, GameBuilder
from Infernux.engine import nuitka_builder as nuitka_builder_module
from Infernux.engine.nuitka_builder import NuitkaBuilder


def _make_project(tmp_path):
    project_root = tmp_path / "project"
    settings_dir = project_root / "ProjectSettings"
    settings_dir.mkdir(parents=True)
    scene_path = project_root / "main.scene"
    scene_path.write_text("scene", encoding="utf-8")
    (settings_dir / "BuildSettings.json").write_text(
        json.dumps({"scenes": [str(scene_path)]}, ensure_ascii=False),
        encoding="utf-8",
    )
    return project_root


def _make_builder(tmp_path, output_dir):
    project_root = _make_project(tmp_path)
    return GameBuilder(str(project_root), str(output_dir), game_name="TestGame")


def _write_asset_script(project_root, relative_path: str, source: str) -> None:
    script_path = project_root / "Assets" / relative_path
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(source, encoding="utf-8")


class TestGameBuilderOutputSafety:
    def test_validate_rejects_non_empty_unmarked_output_dir(self, tmp_path):
        output_dir = tmp_path / "build_output"
        output_dir.mkdir()
        keep_file = output_dir / "keep.txt"
        keep_file.write_text("keep", encoding="utf-8")
        builder = _make_builder(tmp_path, output_dir)

        with pytest.raises(BuildOutputDirectoryError) as exc_info:
            builder._validate()

        assert exc_info.value.reason == "not-empty-unmarked"
        assert exc_info.value.entries == ["keep.txt"]

        assert keep_file.read_text(encoding="utf-8") == "keep"

    def test_validate_allows_only_build_temp_output_dir(self, tmp_path):
        output_dir = tmp_path / "build_output"
        temp_dir = output_dir / "_build_temp"
        nested_dir = temp_dir / "nested"
        nested_dir.mkdir(parents=True)
        (nested_dir / "stale.bin").write_bytes(b"stale")
        builder = _make_builder(tmp_path, output_dir)

        builder._validate()

    def test_clean_output_allows_marked_build_directory(self, tmp_path):
        output_dir = tmp_path / "build_output"
        output_dir.mkdir()
        old_file = output_dir / "old.bin"
        old_file.write_text("old", encoding="utf-8")
        nested_dir = output_dir / "Data"
        nested_dir.mkdir()
        (nested_dir / "stale.txt").write_text("stale", encoding="utf-8")

        builder = _make_builder(tmp_path, output_dir)
        builder._write_output_marker(str(output_dir))

        builder._validate()
        builder._clean_output()

        assert output_dir.is_dir()
        assert list(output_dir.iterdir()) == []

    def test_write_output_marker_creates_reusable_build_marker(self, tmp_path):
        output_dir = tmp_path / "build_output"
        output_dir.mkdir()
        builder = _make_builder(tmp_path, output_dir)

        builder._write_output_marker(str(output_dir))

        marker_path = output_dir / GameBuilder.OUTPUT_MARKER_FILENAME
        assert marker_path.is_file()
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
        assert payload["tool"] == "Infernux"
        assert payload["kind"] == "build-output"
        assert payload["project_name"] == "TestGame"


class TestGameBuilderDependencyCollection:
    def test_collect_user_dependencies_excludes_mcp_packages_from_requirements(self, tmp_path, monkeypatch):
        project_root = _make_project(tmp_path)
        (project_root / "requirements.txt").write_text(
            "mcp>=1.24,<2\nfastmcp\n",
            encoding="utf-8",
        )
        builder = GameBuilder(str(project_root), str(tmp_path / "build_output"), game_name="TestGame")

        def fake_find_spec(name):
            assert name not in {"mcp", "fastmcp"}
            return None

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

        assert builder._collect_user_dependencies() == []

    def test_collect_user_dependencies_excludes_mcp_packages_from_asset_imports(self, tmp_path, monkeypatch):
        project_root = _make_project(tmp_path)
        _write_asset_script(project_root, "tooling.py", "import mcp\nimport fastmcp\n")
        builder = GameBuilder(str(project_root), str(tmp_path / "build_output"), game_name="TestGame")

        def fake_find_spec(name):
            assert name not in {"mcp", "fastmcp"}
            return None

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

        assert builder._collect_user_dependencies() == []

    def test_project_requirement_files_filters_mcp_for_game_build(self, tmp_path):
        project_root = _make_project(tmp_path)
        req_path = project_root / "requirements.txt"
        req_path.write_text(
            "# keep comments\n"
            "mcp>=1.24,<2\n"
            "requests>=2\n"
            "fastmcp\n",
            encoding="utf-8",
        )
        builder = GameBuilder(str(project_root), str(tmp_path / "build_output"), game_name="TestGame")

        filtered_files = builder._project_requirement_files()

        assert len(filtered_files) == 1
        filtered_text = open(filtered_files[0], "r", encoding="utf-8").read()
        assert "requests>=2" in filtered_text
        assert "mcp" not in filtered_text.lower()
        assert "fastmcp" not in filtered_text.lower()
        assert "mcp>=1.24,<2" in req_path.read_text(encoding="utf-8")

    def test_filter_shipped_requirements_removes_mcp_and_disabled_jit(self, tmp_path):
        data_dir = tmp_path / "build_output" / "Data"
        settings_dir = data_dir / "ProjectSettings"
        settings_dir.mkdir(parents=True)
        req_path = settings_dir / "requirements.txt"
        req_path.write_text(
            "numba>=0.61.0\n"
            "mcp>=1.24,<2\n"
            "fastmcp\n"
            "requests>=2\n",
            encoding="utf-8",
        )
        builder = _make_builder(tmp_path, tmp_path / "build_output")

        builder._filter_shipped_requirements(str(data_dir))

        filtered_text = req_path.read_text(encoding="utf-8")
        assert "requests>=2" in filtered_text
        assert "numba" not in filtered_text.lower()
        assert "mcp" not in filtered_text.lower()
        assert "fastmcp" not in filtered_text.lower()

    def test_nuitka_builder_treats_mcp_as_game_build_excluded(self):
        assert NuitkaBuilder._is_game_build_excluded_package("mcp")
        assert NuitkaBuilder._is_game_build_excluded_package("fastmcp.server")
        assert not NuitkaBuilder._is_game_build_excluded_package("requests")

    def test_collect_user_dependencies_adds_llvmlite_for_numba_import(self, tmp_path, monkeypatch):
        project_root = _make_project(tmp_path)
        _write_asset_script(project_root, "stress.py", "import numba\n")
        builder = GameBuilder(str(project_root), str(tmp_path / "build_output"), game_name="TestGame")

        original_find_spec = importlib.util.find_spec

        def fake_find_spec(name):
            if name in {"numba", "llvmlite", "numpy"}:
                return object()
            return original_find_spec(name)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

        deps = builder._collect_user_dependencies()

        assert deps == ["llvmlite", "numba", "numpy"]


class TestGameBuilderAutoParallelExport:
    def test_compile_user_scripts_emits_auto_parallel_sidecar_pyc(self, tmp_path):
        output_dir = tmp_path / "build_output"
        assets_dir = output_dir / "Data" / "Assets"
        assets_dir.mkdir(parents=True)

        script_path = assets_dir / "stress.py"
        script_path.write_text(
            "from Infernux.jit import njit\n"
            "@njit(cache=True, auto_parallel=True)\n"
            "def burn(n):\n"
            "    acc = 0\n"
            "    for i in range(n):\n"
            "        acc += i\n"
            "    return acc\n",
            encoding="utf-8",
        )

        builder = _make_builder(tmp_path, output_dir)
        builder._compile_user_scripts(str(output_dir))

        assert not script_path.exists()
        assert (assets_dir / "stress.pyc").is_file()
        assert (assets_dir / "stress.autop.pyc").is_file()

    def test_compile_user_scripts_skips_sidecar_for_non_auto_parallel_script(self, tmp_path):
        output_dir = tmp_path / "build_output"
        assets_dir = output_dir / "Data" / "Assets"
        assets_dir.mkdir(parents=True)

        script_path = assets_dir / "plain.py"
        script_path.write_text(
            "from Infernux.jit import njit\n"
            "@njit(cache=True)\n"
            "def burn(n):\n"
            "    acc = 0\n"
            "    for i in range(n):\n"
            "        acc += i\n"
            "    return acc\n",
            encoding="utf-8",
        )

        builder = _make_builder(tmp_path, output_dir)
        builder._compile_user_scripts(str(output_dir))

        assert not script_path.exists()
        assert (assets_dir / "plain.pyc").is_file()
        assert not (assets_dir / "plain.autop.pyc").exists()

    def test_collect_user_dependencies_detects_public_infernux_jit_api(self, tmp_path, monkeypatch):
        project_root = _make_project(tmp_path)
        _write_asset_script(project_root, "jit_user.py", "from Infernux.jit import njit\n")
        builder = GameBuilder(str(project_root), str(tmp_path / "build_output"), game_name="TestGame")

        original_find_spec = importlib.util.find_spec

        def fake_find_spec(name):
            if name in {"numba", "llvmlite", "numpy"}:
                return object()
            return original_find_spec(name)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

        deps = builder._collect_user_dependencies()

        assert deps == ["llvmlite", "numba", "numpy"]


class TestNuitkaWindowsSdkEnvironment:
    def test_augment_windows_sdk_environment_adds_kits_tools_and_paths(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nuitka_builder_module.sys, "platform", "win32")

        sdk_root = tmp_path / "Windows Kits" / "10"
        sdk_version = "10.0.22621.0"
        for relative_dir in (
            f"Include/{sdk_version}/ucrt",
            f"Include/{sdk_version}/shared",
            f"Include/{sdk_version}/um",
            f"Include/{sdk_version}/winrt",
            f"Lib/{sdk_version}/ucrt/x64",
            f"Lib/{sdk_version}/um/x64",
            f"bin/{sdk_version}/x64",
        ):
            (sdk_root / relative_dir).mkdir(parents=True, exist_ok=True)
        (sdk_root / "Include" / sdk_version / "um" / "Windows.h").write_text("", encoding="utf-8")

        for tool_name in ("rc.exe", "mt.exe"):
            tool_path = sdk_root / "bin" / sdk_version / "x64" / tool_name
            tool_path.write_text("", encoding="utf-8")
            tool_path.chmod(0o755)

        msvc_bin = tmp_path / "msvc" / "bin"
        msvc_bin.mkdir(parents=True)
        for tool_name in ("cl.exe", "link.exe"):
            tool_path = msvc_bin / tool_name
            tool_path.write_text("", encoding="utf-8")
            tool_path.chmod(0o755)
        msvc_include = tmp_path / "msvc" / "include"
        msvc_lib = tmp_path / "msvc" / "lib" / "x64"
        msvc_include.mkdir(parents=True)
        msvc_lib.mkdir(parents=True)
        (msvc_include / "excpt.h").write_text("", encoding="utf-8")
        (msvc_lib / "vcruntime.lib").write_text("", encoding="utf-8")

        monkeypatch.setattr(nuitka_builder_module, "_windows_sdk_roots_from_registry", lambda: [str(sdk_root)])
        env = {
            "PATH": str(msvc_bin),
            "INCLUDE": str(msvc_include),
            "LIB": str(msvc_lib),
        }

        augmented = nuitka_builder_module._augment_windows_sdk_environment(env)
        forced = nuitka_builder_module._force_msvc_tool_variables(augmented)

        assert nuitka_builder_module._msvc_env_ready(forced)
        assert str(sdk_root / "bin" / sdk_version / "x64") in forced["PATH"]
        assert str(sdk_root / "Include" / sdk_version / "um") in forced["INCLUDE"]
        assert str(sdk_root / "Lib" / sdk_version / "um" / "x64") in forced["LIB"]
        assert str(sdk_root / "Lib" / sdk_version / "um" / "x64") in forced["LIBPATH"]
        assert forced["WindowsSdkBinPath"].rstrip("\\/").endswith(str(sdk_root / "bin" / sdk_version / "x64"))
        assert forced["UniversalCRTSdkDir"].rstrip("\\/").endswith(str(sdk_root))
        assert forced["MSSDK_DIR"].rstrip("\\/").endswith(str(sdk_root))
        assert forced["WindowsSDKVersion"] == sdk_version
        assert forced["CC"].endswith("cl.exe")
        assert forced["CXX"].endswith("cl.exe")
        assert "LINK" not in forced
        assert forced["RC"].endswith("rc.exe")
        assert forced["MT"].endswith("mt.exe")

    def test_force_msvc_tool_variables_removes_link_environment_options(self, tmp_path):
        tool_dir = tmp_path / "Program Files" / "MSVC" / "bin"
        tool_dir.mkdir(parents=True)
        for tool_name in ("cl.exe", "link.exe", "rc.exe", "mt.exe"):
            tool_path = tool_dir / tool_name
            tool_path.write_text("", encoding="utf-8")
            tool_path.chmod(0o755)

        forced = nuitka_builder_module._force_msvc_tool_variables({
            "PATH": str(tool_dir),
            "LINK": str(tool_dir / "link.exe"),
            "_LINK_": str(tool_dir / "link.exe"),
        })

        assert forced["CC"].endswith("cl.exe")
        assert forced["CXX"].endswith("cl.exe")
        assert "LINK" not in forced
        assert "_LINK_" not in forced
        assert forced["RC"].endswith("rc.exe")
        assert forced["MT"].endswith("mt.exe")

    def test_sdk_only_environment_is_not_ready_without_msvc_headers_and_libs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nuitka_builder_module.sys, "platform", "win32")

        sdk_root = tmp_path / "Windows Kits" / "10"
        sdk_version = "10.0.26100.0"
        for relative_dir in (
            f"Include/{sdk_version}/ucrt",
            f"Include/{sdk_version}/shared",
            f"Include/{sdk_version}/um",
            f"Lib/{sdk_version}/ucrt/x64",
            f"Lib/{sdk_version}/um/x64",
            f"bin/{sdk_version}/x64",
        ):
            (sdk_root / relative_dir).mkdir(parents=True, exist_ok=True)
        (sdk_root / "Include" / sdk_version / "um" / "Windows.h").write_text("", encoding="utf-8")
        for tool_name in ("rc.exe", "mt.exe"):
            tool_path = sdk_root / "bin" / sdk_version / "x64" / tool_name
            tool_path.write_text("", encoding="utf-8")
            tool_path.chmod(0o755)

        msvc_bin = tmp_path / "msvc" / "bin"
        msvc_bin.mkdir(parents=True)
        for tool_name in ("cl.exe", "link.exe"):
            tool_path = msvc_bin / tool_name
            tool_path.write_text("", encoding="utf-8")
            tool_path.chmod(0o755)

        monkeypatch.setattr(nuitka_builder_module, "_windows_sdk_roots_from_registry", lambda: [str(sdk_root)])
        env = nuitka_builder_module._augment_windows_sdk_environment({"PATH": str(msvc_bin)})

        missing = nuitka_builder_module._msvc_env_missing_parts(env)
        assert "MSVC INCLUDE (excpt.h)" in missing
        assert "MSVC LIB (vcruntime.lib)" in missing
        assert not nuitka_builder_module._msvc_env_ready(env)

    def test_windows_sdk_roots_include_explicit_override(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nuitka_builder_module.sys, "platform", "win32")
        sdk_root = tmp_path / "custom-sdk"
        sdk_root.mkdir()
        monkeypatch.setenv("INFERNUX_WINDOWS_SDK_DIR", str(sdk_root))
        monkeypatch.setattr(nuitka_builder_module, "_windows_sdk_roots_from_registry", lambda: [])

        assert str(sdk_root) in nuitka_builder_module._windows_sdk_roots({})

    def test_msvc_environment_scripts_include_explicit_vs_root(self, tmp_path, monkeypatch):
        vs_root = tmp_path / "VS"
        script_path = vs_root / "Common7" / "Tools" / "VsDevCmd.bat"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("", encoding="utf-8")
        monkeypatch.setenv("INFERNUX_VSINSTALLDIR", str(vs_root))
        monkeypatch.delenv("INFERNUX_VCVARSALL", raising=False)
        monkeypatch.setattr(nuitka_builder_module, "_visual_studio_roots_from_vswhere", lambda: [])
        monkeypatch.setattr(nuitka_builder_module, "_visual_studio_roots_from_registry", lambda: [])

        assert (str(script_path), ["-arch=x64", "-host_arch=x64"]) in nuitka_builder_module._find_msvc_environment_scripts()

    def test_windows_nuitka_command_does_not_force_msvc_latest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nuitka_builder_module.sys, "platform", "win32")
        monkeypatch.setattr(nuitka_builder_module, "_has_msvc_toolchain", lambda: True)

        builder = object.__new__(NuitkaBuilder)
        builder._builder_python = "python"
        builder.console_mode = "disable"
        builder._staging_dir = str(tmp_path / "stage")
        builder.output_filename = "Game.exe"
        builder.lto = False
        builder.extra_include_packages = []
        builder.extra_include_data = []
        builder.raw_copy_packages = []
        builder.product_name = "Game"
        builder.file_version = "1.0.0.0"
        builder.icon_path = None
        builder._staged_entry = str(tmp_path / "boot.py")

        cmd = builder._build_command()

        assert "--msvc=latest" not in cmd
