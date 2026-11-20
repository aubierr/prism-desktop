"""Marker for power commands sent by Home Assistant (fork feature)."""

COMMAND_PREFIX = "command_"


def is_command(message) -> bool:
    """True for any 'command_*' message, known or not, so unknown commands are
    swallowed instead of being shown as a notification."""
    return isinstance(message, str) and message.strip().lower().startswith(COMMAND_PREFIX)
