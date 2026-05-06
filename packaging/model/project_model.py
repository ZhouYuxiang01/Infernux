import datetime
import os
import sys
import json
import subprocess
import shutil
import glob
import zipfile

from hub_utils import is_frozen, is_project_open
from python_runtime import PythonRuntimeError, PythonRuntimeManager
import logging

# Suppress console windows for all child processes on Windows
_NO_WINDOW: int = 0x08000000 if sys.platform == "win32" else 0


def _popen_kwargs(*, capture_output: bool = False) -> dict:
    """Common subprocess kwargs: suppress console window for child processes.

    When capture_output is True we collect stdout/stderr so the UI can show a
    meaningful failure message instead of hanging indefinitely.
    """
    kw: dict = {
        "stdin": subprocess.DEVNULL,
        "env": {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    }
    if capture_output:
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE
        kw["text"] = True
        kw["encoding"] = "utf-8"
        kw["errors"] = "replace"
    else:
        kw["stdout"] = subprocess.DEVNULL
        kw["stderr"] = subprocess.DEVNULL
    if sys.platform == "win32":
        kw["creationflags"] = _NO_WINDOW
    return kw


def _run_hidden(args: list[str], *, timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            check=True,
            timeout=timeout,
            **_popen_kwargs(capture_output=True),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Command timed out after {timeout} s.\n{' '.join(args)}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = _summarize_output(exc.stderr or exc.stdout)
        raise RuntimeError(
            f"Command failed (exit code {exc.returncode}).\n{' '.join(args)}\n{details}"
        ) from exc


def _summarize_output(output: str) -> str:
    text = (output or "").strip()
    if not text:
        return "No diagnostic output was produced."
    lines = text.splitlines()
    return "\n".join(lines[-20:])


_NATIVE_IMPORT_SMOKE_TEST = (
    "import Infernux.lib\n"
    "print('INFERNUX_NATIVE_IMPORT_OK')\n"
)


def _find_dev_wheel() -> str:
    """Find the Infernux wheel in the dist/ directory next to the engine source.

    Only used in dev mode (non-frozen).
    """
    engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dist_dir = os.path.join(engine_root, "dist")
    wheels = glob.glob(os.path.join(dist_dir, "infernux-*.whl"))
    if wheels:
        wheels.sort(key=os.path.getmtime, reverse=True)
        return wheels[0]
    return ""


def _wheel_version_from_path(wheel_path: str) -> str:
    name = os.path.basename(wheel_path or "")
    if not name.lower().endswith(".whl"):
        return ""
    parts = name[:-4].split("-")
    if len(parts) < 2:
        return ""
    distribution = parts[0].replace("_", "-").lower()
    if distribution != "infernux":
        return ""
    return parts[1]


def _installed_distribution_version(python_exe: str, distribution_name: str) -> str:
    script = (
        "import importlib.metadata as metadata, sys; "
        "name = sys.argv[1]; "
        "\ntry:\n"
        "    print(metadata.version(name))\n"
        "except metadata.PackageNotFoundError:\n"
        "    raise SystemExit(1)\n"
    )
    try:
        completed = subprocess.run(
            [python_exe, "-c", script, distribution_name],
            timeout=30,
            **_popen_kwargs(capture_output=True),
        )
    except (OSError, subprocess.SubprocessError) as _exc:
        logging.getLogger(__name__).debug("[Suppressed] %s: %s", type(_exc).__name__, _exc)
        return ""
    if completed.returncode != 0:
        return ""
    return (completed.stdout or "").strip()


def _distribution_files_present(site_packages: str, distribution_name: str) -> bool:
    if not os.path.isdir(site_packages):
        return False
    normalized = distribution_name.replace("-", "_").lower()
    dist_info_prefix = distribution_name.replace("_", "-").lower() + "-"
    try:
        names = os.listdir(site_packages)
    except OSError as _exc:
        logging.getLogger(__name__).debug("[Suppressed] %s: %s", type(_exc).__name__, _exc)
        return False
    for name in names:
        lower_name = name.lower()
        if lower_name == normalized:
            return True
        if lower_name.startswith(dist_info_prefix) and lower_name.endswith(".dist-info"):
            return True
    return False


def _remove_tree(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    if sys.platform == "win32":
        completed = subprocess.run(
            ["cmd", "/c", "rd", "/s", "/q", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
        )
        if completed.returncode == 0 and not os.path.exists(path):
            return
    shutil.rmtree(path, ignore_errors=True)


def _safe_wheel_member_path(name: str) -> str:
    normalized = name.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        return ""
    return os.path.join(*parts)


def _wheel_target_relative_path(member_name: str) -> str:
    safe_name = _safe_wheel_member_path(member_name)
    if not safe_name:
        return ""
    parts = safe_name.split(os.sep)
    if len(parts) >= 3 and parts[0].endswith(".data") and parts[1] in {"purelib", "platlib"}:
        return os.path.join(*parts[2:])
    if len(parts) >= 2 and parts[0].endswith(".data"):
        return ""
    return safe_name


def _remove_installed_distribution(site_packages: str, distribution_name: str) -> None:
    normalized_package = distribution_name.replace("-", "_").lower()
    dist_info_prefix = distribution_name.replace("_", "-").lower() + "-"
    try:
        names = os.listdir(site_packages)
    except OSError as _exc:
        logging.getLogger(__name__).debug("[Suppressed] %s: %s", type(_exc).__name__, _exc)
        return

    for name in names:
        lower_name = name.lower()
        if lower_name == normalized_package or (
            lower_name.startswith(dist_info_prefix) and lower_name.endswith(".dist-info")
        ):
            path = os.path.join(site_packages, name)
            if os.path.isdir(path) and not os.path.islink(path):
                _remove_tree(path)
            else:
                try:
                    os.remove(path)
                except OSError as _exc:
                    logging.getLogger(__name__).debug("[Suppressed] %s: %s", type(_exc).__name__, _exc)


def _install_wheel_direct(wheel_path: str, site_packages: str, distribution_name: str) -> None:
    os.makedirs(site_packages, exist_ok=True)
    _remove_installed_distribution(site_packages, distribution_name)

    try:
        with zipfile.ZipFile(wheel_path) as wheel:
            for member in wheel.infolist():
                target_relative = _wheel_target_relative_path(member.filename)
                if not target_relative:
                    continue
                target_path = os.path.join(site_packages, target_relative)
                if member.is_dir():
                    os.makedirs(target_path, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with wheel.open(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
    except (OSError, zipfile.BadZipFile) as exc:
        raise RuntimeError(
            f"Failed to install the Infernux wheel into the project runtime.\n{wheel_path}\n{exc}"
        ) from exc


class ProjectModel:
    def __init__(self, db, version_manager=None, runtime_manager=None):
        self.db = db
        self.version_manager = version_manager
        self.runtime_manager = runtime_manager or PythonRuntimeManager()

    def add_project(self, name, path):
        return self.db.add_project(name, path)

    def delete_project(self, name):
        base_path = self.db.get_project_path(name)
        project_dir = os.path.join(base_path, name) if base_path else ""

        if project_dir and is_project_open(project_dir):
            raise RuntimeError(
                f"The project is currently open in Infernux and cannot be deleted:\n{project_dir}"
            )

        if project_dir and os.path.exists(project_dir):
            try:
                shutil.rmtree(project_dir)
            except OSError as exc:
                raise RuntimeError(
                    f"Failed to remove the project folder:\n{project_dir}\n{exc}"
                ) from exc

        self.db.delete_project(name)

    
    def init_project_folder(self, project_name: str, project_path: str,
                            engine_version: str = "", on_status=None):
        if on_status:
            on_status("Creating project folders...")
        project_dir = os.path.join(project_path, project_name)
        os.makedirs(project_dir, exist_ok=True)

        # Create subdirectories
        for subdir in ("ProjectSettings", "Logs", "Library", "Assets"):
            os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)

        # Create a README file in assets
        readme_path = os.path.join(project_dir, "Assets", "README.md")
        with open(readme_path, "w") as f:
            f.write("# Project Assets\n\nThis folder contains all the assets for the project.\n")

        # Create default project requirements
        req_path = os.path.join(project_dir, "ProjectSettings", "requirements.txt")
        if not os.path.isfile(req_path):
            self._copy_bundled_requirements(req_path, engine_version)

        # Create .ini file in project path
        ini_path = os.path.join(project_dir, f"{project_name}.ini")
        now = datetime.datetime.now()
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write("[Project]\n")
            f.write(f"name = {project_name}\n")
            f.write(f"path = {project_dir}\n")
            f.write(f"created_at = {now}\n")
            f.write(f"changed_at = {now}\n")

        # ── Pin engine version ──────────────────────────────────────────
        if engine_version:
            from version_manager import VersionManager
            VersionManager.write_project_version(project_dir, engine_version)

        # ── Create project Python runtime and install Infernux ────────
        runtime_path = os.path.join(project_dir, ".runtime", "python312")
        try:
            self._create_project_runtime(project_dir, on_status=on_status)
            self._install_infernux_in_runtime(project_dir, engine_version, on_status=on_status)
        except Exception:
            shutil.rmtree(os.path.join(project_dir, ".runtime"), ignore_errors=True)
            raise

        # ── Create VS Code workspace configuration ─────────────────────
        if on_status:
            on_status("Writing project editor settings...")
        self._create_vscode_workspace(project_dir)

    # -----------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------

    def _copy_bundled_requirements(self, dest_path: str, engine_version: str) -> None:
        """Copy the default requirements.txt to *dest_path*.

        Resolves the file from the source tree (dev mode) or extracts it
        from the engine wheel, avoiding any ``import Infernux`` in the Hub
        process (which doesn't have the engine package installed).
        """
        import zipfile

        # 1) Dev mode: resolve from the source tree next to this repo
        engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        source_req = os.path.join(
            engine_root, "python", "Infernux", "resources", "supports", "requirements.txt",
        )
        if os.path.isfile(source_req):
            shutil.copy2(source_req, dest_path)
            return

        # 2) Extract from the wheel (a zip file)
        wheel = ""
        if engine_version and self.version_manager is not None:
            wheel = self.version_manager.get_wheel_path(engine_version) or ""
        if not wheel and not is_frozen():
            wheel = _find_dev_wheel()
        if wheel and os.path.isfile(wheel):
            try:
                with zipfile.ZipFile(wheel) as zf:
                    for name in zf.namelist():
                        if name.endswith("resources/supports/requirements.txt"):
                            with zf.open(name) as src, open(dest_path, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                            return
            except zipfile.BadZipFile as _exc:
                logging.getLogger(__name__).debug("[Suppressed] %s: %s", type(_exc).__name__, _exc)
                pass

    @staticmethod
    def _get_project_python(project_dir: str) -> str:
        """Return the Python executable for the project.

        In frozen (packaged Hub) mode, each project owns a full Python copy
        under .runtime/python312/.  In dev mode, we use a classic .venv.
        """
        if is_frozen():
            runtime_dir = os.path.join(project_dir, ".runtime", "python312")
            if sys.platform == "win32":
                return os.path.join(runtime_dir, "python.exe")
            return os.path.join(runtime_dir, "bin", "python")
        # Dev mode: classic .venv
        venv_dir = os.path.join(project_dir, ".venv")
        if sys.platform == "win32":
            return os.path.join(venv_dir, "Scripts", "python.exe")
        return os.path.join(venv_dir, "bin", "python")

    def _create_project_runtime(self, project_dir: str, *, on_status=None) -> None:
        if is_frozen():
            runtime_path = os.path.join(project_dir, ".runtime", "python312")
            try:
                self.runtime_manager.create_project_runtime(runtime_path, on_status=on_status)
            except PythonRuntimeError as exc:
                raise RuntimeError(str(exc)) from exc
            return

        # Dev mode: create a classic .venv
        venv_path = os.path.join(project_dir, ".venv")
        if on_status:
            on_status("Creating project virtual environment...")
        _run_hidden([sys.executable, "-m", "venv", "--copies", venv_path], timeout=600)

    def _install_infernux_in_runtime(self, project_dir: str, engine_version: str = "", *, on_status=None):
        """Install the Infernux wheel into the project's Python environment.

        In frozen (packaged Hub) mode, the wheel is installed into the project's
        full Python copy at .runtime/python312/.
        In dev mode, the wheel is installed into the classic .venv.

        Source builds are intentionally blocked here so project creation never
        falls back to a local C++ compile.
        """
        project_python = ProjectModel._get_project_python(project_dir)
        if not os.path.isfile(project_python):
            raise RuntimeError(
                f"Project Python not found at {project_python}.\n"
                "The project runtime may not have been created correctly."
            )

        wheel = ""

        if engine_version and self.version_manager is not None:
            wheel = self.version_manager.get_wheel_path(engine_version) or ""

        if not wheel and not is_frozen():
            wheel = _find_dev_wheel()

        if not wheel:
            if is_frozen():
                raise RuntimeError(
                    f"No downloaded Infernux wheel was found for version {engine_version or '(unknown)'}.\n"
                    "Open the Installs page and install that engine version first."
                )
            raise RuntimeError(
                "No prebuilt Infernux wheel was found in dist/.\n"
                "Build a wheel first; project creation will not fall back to a source build."
            )

        target_version = _wheel_version_from_path(wheel)
        if on_status:
            on_status("Installing Infernux into the project runtime...")
        installed_version = ""
        site_packages = ProjectModel._get_site_packages(project_dir)
        if _distribution_files_present(site_packages, "Infernux"):
            installed_version = _installed_distribution_version(project_python, "Infernux")
        if target_version and installed_version == target_version:
            try:
                ProjectModel.validate_python_runtime(project_python)
                return
            except RuntimeError as _exc:
                logging.getLogger(__name__).debug("[Suppressed] %s: %s", type(_exc).__name__, _exc)

        if is_frozen():
            if on_status:
                on_status("Installing Infernux engine files...")
            _install_wheel_direct(wheel, site_packages, "Infernux")
            if on_status:
                on_status("Validating project runtime...")
            ProjectModel.validate_python_runtime(project_python)
            return

        _PIP_FLAGS = [
            "--no-input",
            "--disable-pip-version-check",
            "--prefer-binary",
            "--only-binary=:all:",
            "--no-cache-dir",
        ]

        pip_args = [project_python, "-m", "pip", "install", *_PIP_FLAGS]
        pip_args.append("--force-reinstall")
        pip_args.append(wheel)

        _run_hidden(pip_args, timeout=600)
        if on_status:
            on_status("Validating project runtime...")
        ProjectModel.validate_python_runtime(project_python)

    @staticmethod
    def validate_python_runtime(project_python: str) -> None:
        if not os.path.isfile(project_python):
            raise RuntimeError(
                f"Project Python not found at {project_python}.\n"
                "The project runtime may not have been created correctly."
            )

        _run_hidden([project_python, "-c", _NATIVE_IMPORT_SMOKE_TEST], timeout=120)

    @staticmethod
    def validate_project_runtime(project_dir: str) -> None:
        ProjectModel.validate_python_runtime(ProjectModel._get_project_python(project_dir))

    @staticmethod
    def _get_site_packages(project_dir: str) -> str:
        """Return the site-packages directory for the project's Python runtime."""
        if is_frozen():
            runtime_dir = os.path.join(project_dir, ".runtime", "python312")
            if sys.platform == "win32":
                return os.path.join(runtime_dir, "Lib", "site-packages")
            return os.path.join(runtime_dir, "lib", "python3.12", "site-packages")
        venv_dir = os.path.join(project_dir, ".venv")
        if sys.platform == "win32":
            return os.path.join(venv_dir, "Lib", "site-packages")
        return os.path.join(venv_dir, "lib", "python3.12", "site-packages")

    @staticmethod
    def _create_vscode_workspace(project_dir: str):
        """
        Create .vscode/ config so that opening any file inside the project
        uses the correct Python interpreter and gets full Infernux autocompletion.
        """
        vscode_dir = os.path.join(project_dir, ".vscode")
        os.makedirs(vscode_dir, exist_ok=True)

        # ── settings.json ───────────────────────────────────────────────
        project_python = ProjectModel._get_project_python(project_dir)
        site_packages = ProjectModel._get_site_packages(project_dir)
        vscode_python = ProjectModel._vscode_python_path(project_dir)
        settings = {
            "python.defaultInterpreterPath": vscode_python,
            "python.pythonPath": vscode_python,
            "python.terminal.activateEnvironment": True,
            "python.analysis.typeCheckingMode": "basic",
            "python.analysis.autoImportCompletions": True,
            "python.analysis.extraPaths": [site_packages],
            "python.analysis.diagnosticSeverityOverrides": {
                "reportMissingModuleSource": "none",
            },
            "editor.formatOnSave": True,
            "files.exclude": {
                "**/__pycache__": True,
                "**/*.pyc": True,
                "**/*.meta": True,
                ".venv": True,
                ".runtime": True,
                "Library": True,
                "Logs": True,
                "ProjectSettings": True,
            },
        }
        settings_path = os.path.join(vscode_dir, "settings.json")
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)

        # ── extensions.json ─────────────────────────────────────────────
        extensions = {
            "recommendations": [
                "ms-python.python",
                "ms-python.vscode-pylance",
            ]
        }
        extensions_path = os.path.join(vscode_dir, "extensions.json")
        with open(extensions_path, "w", encoding="utf-8") as f:
            json.dump(extensions, f, indent=4, ensure_ascii=False)

        # ── pyrightconfig.json (at project root) ────────────────────────
        # In frozen mode, point Pyright directly at the project runtime Python;
        # in dev mode, use the classic venvPath/venv convention.
        if is_frozen():
            pyright_config = {
                "pythonPath": ProjectModel._get_project_python(project_dir),
                "pythonVersion": "3.12",
                "typeCheckingMode": "basic",
                "reportMissingModuleSource": False,
                "reportWildcardImportFromLibrary": False,
                "extraPaths": [site_packages],
                "include": ["Assets"],
            }
        else:
            pyright_config = {
                "venvPath": ".",
                "venv": ".venv",
                "pythonPath": ProjectModel._vscode_python_path(project_dir),
                "pythonVersion": "3.12",
                "typeCheckingMode": "basic",
                "reportMissingModuleSource": False,
                "reportWildcardImportFromLibrary": False,
                "extraPaths": [site_packages],
                "include": ["Assets"],
            }
        pyright_path = os.path.join(project_dir, "pyrightconfig.json")
        with open(pyright_path, "w", encoding="utf-8") as f:
            json.dump(pyright_config, f, indent=4, ensure_ascii=False)

    @staticmethod
    def _vscode_python_path(project_dir: str) -> str:
        """Return the interpreter path VSCode should store in settings.json."""
        if is_frozen():
            return ProjectModel._get_project_python(project_dir).replace("\\", "/")
        if sys.platform == "win32":
            return "${workspaceFolder}/.venv/Scripts/python.exe"
        return "${workspaceFolder}/.venv/bin/python"