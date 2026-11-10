import json
from unittest.mock import Mock

from desktop import app
from desktop.bridge import DesktopBridge, DesktopController


def test_set_data_dir_persists_for_the_next_launcher_start(tmp_path):
    preferences = tmp_path / "settings" / "desktop.json"
    selected_directory = tmp_path / "chosen-data"
    selected_directory.mkdir()
    controller = DesktopController(preferences_path=preferences)

    response = controller.set_data_dir(str(selected_directory))

    assert response == {
        "ok": True,
        "message": "数据目录已保存，将在统一启动器下次启动后端时生效。",
        "data": {"path": str(selected_directory.resolve()), "restart_required": True},
    }
    assert json.loads(preferences.read_text(encoding="utf-8"))["data_dir"] == str(
        selected_directory.resolve()
    )
    assert controller._saved_data_dir() == selected_directory.resolve()


def test_development_mode_does_not_claim_to_manage_external_processes(tmp_path):
    controller = DesktopController(preferences_path=tmp_path / "desktop.json")

    response = controller.start()
    assert response["ok"] is False
    assert "开发模式" in response["message"]
    assert controller.stop()["ok"] is True


def test_start_tracks_the_backend_process_it_created(tmp_path, monkeypatch):
    executable = tmp_path / "ItemTrackingBackend.exe"
    executable.write_bytes(b"test")
    (tmp_path / "frontend").mkdir()
    process = Mock()
    process.poll.return_value = None
    process.pid = 1234
    launched = {}

    def fake_popen(command, **_kwargs):
        launched["command"] = command
        return process

    monkeypatch.setattr("desktop.bridge.subprocess.Popen", fake_popen)
    monkeypatch.setattr("desktop.bridge.APP_ROOT", tmp_path)
    controller = DesktopController(
        preferences_path=tmp_path / "desktop.json",
        backend_command=[str(executable)],
        launch_log_path=tmp_path / "backend-launch.log",
    )
    monkeypatch.setattr(controller, "_wait_until_ready", lambda: (True, ""))

    response = controller.start()

    assert response["ok"] is True
    assert response["data"]["pid"] == 1234
    process.poll.assert_not_called()
    frontend_index = launched["command"].index("--frontend-dir")
    assert launched["command"][frontend_index + 1] == str(tmp_path / "frontend")


def test_source_mode_desktop_uses_the_react_build_directory(tmp_path, monkeypatch):
    frontend_root = tmp_path / "frontend" / "build"
    frontend_root.mkdir(parents=True)
    (frontend_root / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(app, "APP_ROOT", tmp_path)
    monkeypatch.setattr(app.sys, "frozen", False, raising=False)

    resolved = app.frontend_directory()

    assert resolved == frontend_root
    assert (resolved / "index.html").is_file()


def test_stop_sends_shutdown_only_to_the_owned_process(tmp_path, monkeypatch):
    executable = tmp_path / "ItemTrackingBackend.exe"
    executable.write_bytes(b"test")
    process = Mock()
    process.poll.return_value = None
    process.pid = 1234
    process.wait.return_value = 0
    monkeypatch.setattr("desktop.bridge.subprocess.Popen", lambda *args, **kwargs: process)
    controller = DesktopController(
        preferences_path=tmp_path / "desktop.json",
        backend_command=[str(executable)],
    )
    monkeypatch.setattr(controller, "_wait_until_ready", lambda: (True, ""))
    controller.start()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok": true}'

    request_mock = Mock(return_value=Response())
    monkeypatch.setattr("desktop.bridge.urlopen", request_mock)
    response = controller.stop()

    assert response["ok"] is True
    request_mock.assert_called_once()
    process.wait.assert_called_once_with(timeout=10)
    process.terminate.assert_not_called()


def test_export_logs_surfaces_data_lock_failure(tmp_path, monkeypatch):
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    preferences = tmp_path / "desktop.json"
    preferences.write_text(json.dumps({"data_dir": str(data_directory)}), encoding="utf-8")
    destination = tmp_path / "logs.zip"
    completed = Mock(returncode=1, stderr="data directory is locked", stdout="")
    monkeypatch.setattr("desktop.bridge.subprocess.run", lambda *args, **kwargs: completed)

    response = DesktopController(preferences_path=preferences).export_logs(str(destination))

    assert response["ok"] is False
    assert "data directory is locked" in response["message"]


def test_bridge_forwards_the_six_controller_methods_and_shutdown_is_idempotent():
    controller = Mock()
    controller.start.return_value = {"ok": True, "message": "started", "data": None}
    controller.stop.return_value = {"ok": True, "message": "stopped", "data": None}
    controller.open_data_dir.return_value = {"ok": True, "message": "opened", "data": None}
    controller.export_logs.return_value = {"ok": True, "message": "exported", "data": None}
    controller.set_data_dir.return_value = {"ok": True, "message": "saved", "data": None}
    controller.shutdown.return_value = {"ok": True, "message": "closed", "data": None}
    bridge = DesktopBridge(controller)

    assert bridge.start()["ok"]
    assert bridge.stop()["ok"]
    assert bridge.open_data_dir()["ok"]
    assert bridge.export_logs("logs.zip")["ok"]
    assert bridge.set_data_dir("data")["ok"]
    assert bridge.shutdown()["ok"]
    assert bridge.shutdown()["ok"]

    controller.start.assert_called_once_with()
    controller.stop.assert_called_once_with()
    controller.open_data_dir.assert_called_once_with()
    controller.export_logs.assert_called_once_with("logs.zip")
    controller.set_data_dir.assert_called_once_with("data")
    controller.shutdown.assert_called_once_with()
