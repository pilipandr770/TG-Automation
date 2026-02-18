"""Message type enums for conversation handling."""

from enum import Enum


class MessageMode(str, Enum):
    """Message modes for system prompt building."""
    PRIVATE_DIALOG = "private_dialog"
    CHANNEL_COMMENT = "channel_comment"
    PAID_CHANNEL_REPLY = "paid_channel_reply"
