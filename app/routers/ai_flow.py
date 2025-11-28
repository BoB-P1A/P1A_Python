from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict

from ..azure_llm_client import generate_flow_sheets_from_text
from ..schemas_ai import GenerateSheetsRequest, GenerateSheetsResponse, FlowSheets

router = APIRouter(
    prefix="/api/ai",
    tags=["ai"],
)

@router.post("/generate-sheets", response_model=GenerateSheetsResponse)
async def generate_sheets(req: GenerateSheetsRequest):
    # LLM 호출해서 sheets 생성
    sheets = await generate_flow_sheets_from_text(
        company_id=req.company_id,
        task_id=req.task_id,
        plain_text=req.plain_text,
    )
    return {
        "company_id": req.company_id,
        "task_id": req.task_id,
        "sheets": sheets,
    }