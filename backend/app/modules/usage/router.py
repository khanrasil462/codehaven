import re
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.usage import month_usage

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_usage(month: str | None = None) -> dict:
    month = month or datetime.now().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")
    return month_usage(month)
