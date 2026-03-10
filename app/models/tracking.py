from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=50)
    codigo: str = Field(default="", max_length=20)
    tipo: str = Field(default="auto", pattern=r"^(auto|ose|orden)$")


class PersonInfo(BaseModel):
    document: str = ""
    full_name: str = ""


class TimelineStep(BaseModel):
    step: str
    label: str
    date: str | None = None
    completed: bool = False


class TrackingResult(BaseModel):
    ose_id: str
    order_number: str | None = None
    order_code: str | None = None
    sender: PersonInfo = PersonInfo()
    receiver: PersonInfo = PersonInfo()
    status: str = "Sin información"
    timeline: list[TimelineStep] = []
    has_pdf: bool = True
    tracking_url: str = ""
    estimated_delivery: str | None = None


class SearchResponse(BaseModel):
    success: bool
    count: int = 0
    source: str | None = None
    message: str | None = None
    results: list[TrackingResult] = []
