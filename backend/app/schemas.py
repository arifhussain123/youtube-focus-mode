"""Pydantic request/response models."""

from datetime import datetime

from pydantic import BaseModel, Field


class WatchEventIn(BaseModel):
    video_id: str = Field(..., max_length=32)
    title: str = Field(default="", max_length=512)
    channel: str | None = Field(default=None, max_length=256)
    seconds: int = Field(..., ge=0, le=86400)
    # Optional; server stamps "now" (UTC) if the client omits it.
    occurred_at: datetime | None = None


class IngestRequest(BaseModel):
    events: list[WatchEventIn]


class IngestResponse(BaseModel):
    accepted: int


class DailyStat(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    seconds: int


class VideoStat(BaseModel):
    video_id: str
    title: str
    seconds: int


class ChannelStat(BaseModel):
    channel: str
    seconds: int


class CategoryStat(BaseModel):
    category: str
    seconds: int


class Summary(BaseModel):
    today_seconds: int
    week_seconds: int
    total_seconds: int
    daily: list[DailyStat]
    top_videos: list[VideoStat]
    top_channels: list[ChannelStat]
    by_category: list[CategoryStat]


class CategorizeResponse(BaseModel):
    configured: bool
    categorized: int
    remaining: int
