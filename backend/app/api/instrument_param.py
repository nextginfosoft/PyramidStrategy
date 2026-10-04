"""FastAPI dependency: validated `underlying` query parameter (default NIFTY)."""
from fastapi import HTTPException, Query

from app.core.instruments import get_instrument


def underlying_query(underlying: str = Query(default="NIFTY", description="NIFTY or BANKNIFTY")) -> str:
    try:
        return get_instrument(underlying).name
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
