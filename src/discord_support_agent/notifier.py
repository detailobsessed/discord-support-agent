"""macOS notification support."""

import subprocess  # nosec B404


def send_notification(
    title: str,
    message: str,
    subtitle: str | None = None,
    sound: str = "default",
) -> None:
    """Send a macOS notification using osascript.

    Args:
        title: The notification title.
        message: The notification body text.
        subtitle: Optional subtitle.
        sound: Sound name (use "default" for system default, or "" for silent).
    """
    script_parts = [f'display notification "{_escape(message)}" with title "{_escape(title)}"']

    if subtitle:
        script_parts[0] += f' subtitle "{_escape(subtitle)}"'

    if sound:
        script_parts[0] += f' sound name "{sound}"'

    subprocess.run(  # noqa: S603  # nosec B603
        ["/usr/bin/osascript", "-e", script_parts[0]],
        check=False,
        capture_output=True,
    )


def _escape(text: str) -> str:
    """Escape text for AppleScript."""
    return text.replace("\\", "\\\\").replace('"', '\\"')
