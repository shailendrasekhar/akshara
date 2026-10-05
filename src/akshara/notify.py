"""Desktop notifications via org.freedesktop.Notifications, with a beep fallback."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from . import APP_ID, APP_NAME


def notify(title: str, body: str = "", timeout_ms: int = 6000) -> bool:
    """Show a desktop notification. Returns False if only the fallback beep ran."""
    try:
        from PyQt6.QtCore import QMetaType
        from PyQt6.QtDBus import QDBusArgument, QDBusConnection, QDBusInterface, QDBusMessage

        bus = QDBusConnection.sessionBus()
        if bus.isConnected():
            iface = QDBusInterface(
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                bus,
            )
            if iface.isValid():
                # Notify(susssasa{sv}i): replaces_id must be a uint32 and
                # actions a string list, which plain Python values don't map to.
                replaces_id = QDBusArgument(0, QMetaType.Type.UInt.value)  # type: ignore[call-overload]
                actions = QDBusArgument([], QMetaType.Type.QStringList.value)  # type: ignore[call-overload]
                reply = iface.call(
                    "Notify", APP_NAME, replaces_id, APP_ID, title, body, actions, {}, timeout_ms
                )
                if reply.type() != QDBusMessage.MessageType.ErrorMessage:
                    return True
    except Exception:
        pass
    QApplication.beep()
    return False
