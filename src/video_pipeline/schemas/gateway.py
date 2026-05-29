"""Gateway payload schema — normalized user input from Telegram/WhatsApp."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ChannelName = Literal["telegram", "whatsapp"]


class GatewayPayload(BaseModel):
    """Input from OpenClaw gateway → Python orchestrator."""

    raw_prompt: str = Field(min_length=1, description="User natural language request")
    channel: ChannelName
    user_id: str = Field(min_length=1)
    timestamp: datetime
