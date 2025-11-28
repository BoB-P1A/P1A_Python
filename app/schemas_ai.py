from typing import List, Optional
from pydantic import BaseModel, Field

class CollectRow(BaseModel):
    collect_task: str = ""
    collect_target: str = ""
    collect_route: str = ""
    collect_dept: str = ""
    collect_purpose: str = ""
    collect_system: str = ""
    collect_space: str = ""
    collect_bundle: str = ""
    collect_items: str = ""
    collect_online: bool = True
    collect_encrypt: bool = True

class RetainRow(BaseModel):
    retain_task: str = ""
    retain_input_system: str = ""
    retain_space: str = ""
    retain_form: str = ""
    retain_purpose: str = ""
    retain_bundle: str = ""
    retain_items: str = ""
    retain_online: bool = True
    retain_encrypt: bool = True
    retain_enc_items: str = ""

class UseRow(BaseModel):
    use_task: str = ""
    use_space: str = ""
    use_system: str = ""
    use_dept: str = ""
    use_purpose: str = ""
    use_method: str = ""
    use_bundle: str = ""
    use_items: str = ""
    use_online: bool = True
    use_encrypt: bool = True

class ProvideRow(BaseModel):
    provide_task: str = ""
    provide_space: str = ""
    provide_dept: str = ""
    provide_system: str = ""
    provide_sys_online: bool = True
    provide_sys_encrypt: bool = True
    receiver: str = ""
    provide_bundle: str = ""
    provide_items: str = ""
    provide_purpose: str = ""
    provide_method: str = ""
    receiver_online: bool = True
    receiver_encrypt: bool = True

class DiscardRow(BaseModel):
    discard_task: str = ""
    discard_space: str = ""
    discard_system: str = ""
    discard_period: str = ""
    discard_dept: str = ""
    discard_proc: str = ""
    discard_bundle: str = ""
    discard_items: str = ""
    discard_online: bool = True
    discard_encrypt: bool = True

class FlowSheets(BaseModel):
    collect: List[CollectRow] = Field(default_factory=list)
    retain: List[RetainRow] = Field(default_factory=list)
    use: List[UseRow] = Field(default_factory=list)
    provide: List[ProvideRow] = Field(default_factory=list)
    discard: List[DiscardRow] = Field(default_factory=list)

# API용 요청/응답 모델

class GenerateSheetsRequest(BaseModel):
    company_id: str
    task_id: str
    plain_text: str = Field(..., description="업무 설명 텍스트")

class GenerateSheetsResponse(BaseModel):
    company_id: str
    task_id: str
    sheets: FlowSheets
