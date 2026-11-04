from pydantic import BaseModel, Field


class ItemOut(BaseModel):
    code: str
    name: str
    code4: str = Field(description="공영도매 품목코드(4자리)")
    unit: str
    category: str = Field(description="공영 부류")
    emoji: str


class MarketOut(BaseModel):
    code: str = Field(examples=["110001"], description="도매시장 코드 (팀 데이터 매핑_시장.csv)")
    name: str
    sido: str
    sigungu: str
    lat: float
    lon: float


class HorizonOut(BaseModel):
    days: int
    label: str


class RegionOut(BaseModel):
    code: str
    name: str
