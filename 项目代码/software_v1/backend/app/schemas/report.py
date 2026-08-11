from datetime import datetime
from uuid import UUID
from pydantic import Field
from .common import StrictModel

class ReportSummaryResponse(StrictModel):
    report_id: UUID
    task_id: UUID
    status: str
    summary: dict[str, int | float | str]
    created_at: datetime
