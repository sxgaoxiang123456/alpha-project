from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.stock import validate_stock_code


class NaturalLanguageAlertRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    selected_stock_code: str | None = Field(default=None, min_length=6, max_length=6)

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        return value.strip()

    @field_validator("selected_stock_code")
    @classmethod
    def _validate_selected_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_stock_code(value)


class AlertRuleSummary(BaseModel):
    stock_code: str
    stock_name: str
    condition_type: str
    threshold: float


class StockCandidate(BaseModel):
    stock_code: str
    stock_name: str
    sector: str | None = None
    market_cap: float | None = None
    match_score: float = Field(..., ge=0.0, le=1.0)

    @property
    def sort_key(self) -> tuple[float, float]:
        return (-self.match_score, -(self.market_cap or 0.0))


class NaturalLanguageAlertResponse(BaseModel):
    success: bool
    message: str
    rule: AlertRuleSummary | None = None
    candidates: list[StockCandidate] | None = None
