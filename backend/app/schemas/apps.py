from typing import Optional

from pydantic import BaseModel


class AppSearchItem(BaseModel):
    app_id: str
    title: str
    developer: Optional[str] = None
    icon: Optional[str] = None
    score: Optional[float] = None
    genre: Optional[str] = None
    free: Optional[bool] = None
    url: Optional[str] = None


class AppSearchResponse(BaseModel):
    query: str
    count: int
    results: list[AppSearchItem]