from __future__ import annotations

import sys

from akshara.tts import addon


def test_addon_dir_respects_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    d = addon.addon_dir()
    assert d.parent == tmp_path / "akshara" / "tts-addon"
    assert d.name == f"py{sys.version_info.major}.{sys.version_info.minor}"


def test_activate_only_after_complete(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert not addon.activate()
    addon.mark_complete()
    assert addon.is_installed()
    assert addon.activate()
    assert str(addon.addon_dir()) == sys.path[-1]
    addon.activate()
    assert sys.path.count(str(addon.addon_dir())) == 1
    addon.uninstall()
    assert not addon.is_installed()


def test_install_command_targets_addon_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    cmd = addon.install_command()
    if cmd is None:  # neither pip nor uv in this environment
        return
    assert "--target" in cmd and str(addon.addon_dir()) in cmd
    assert addon.TORCH_CPU_INDEX in cmd
    assert any(p.startswith("kokoro") for p in cmd)


def test_dialog_runs_installer_and_marks_complete(qtbot, tmp_path, monkeypatch):
    from akshara.addon_dialog import AddonInstallDialog

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "path", list(sys.path))
    fake = [sys.executable, "-c", "print('Collecting kokoro'); print('Successfully installed')"]
    dlg = AddonInstallDialog(command=fake)
    qtbot.addWidget(dlg)
    with qtbot.waitSignal(dlg.installed, timeout=10000):
        dlg.start()
    assert "Successfully installed" in dlg.log.toPlainText()
    assert addon.is_installed()


def test_dialog_reports_failure(qtbot, tmp_path, monkeypatch):
    from akshara.addon_dialog import AddonInstallDialog

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    dlg = AddonInstallDialog(command=[sys.executable, "-c", "import sys; sys.exit(3)"])
    qtbot.addWidget(dlg)
    with qtbot.waitSignal(dlg.proc.finished, timeout=10000):
        dlg.start()
    assert "exit code 3" in dlg.status.text()
    assert not addon.is_installed()
