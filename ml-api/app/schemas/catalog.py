from pydantic import BaseModel


class ItemOut(BaseModel):
    code: str
    name: str
    unit: str
    category: str
    emoji: str


class RegionOut(BaseModel):
    code: str
    name: str
