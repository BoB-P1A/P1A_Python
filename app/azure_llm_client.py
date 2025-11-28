import os
import json
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

client: Optional[AzureOpenAI] = None
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT:
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )
else:
    # 도커가 죽지 않도록, 그냥 경고 로그만 남김
    print("[WARN] Azure OpenAI env not fully configured. AI API will fail when called.")

# PIA 흐름표용 시스템 프롬프트
SYSTEM_PROMPT = """
당신은 개인정보 영향평가(PIA) 전문가이자 비서입니다.
입력으로 한국어 설명 문서를 받으면, 해당 시스템/업무에 대한 개인정보 흐름표를
아래 JSON 스키마에 맞게 채워야 합니다.

- 흐름 단계는 '수집(collect) / 보유(retain) / 이용(use) / 제공(provide) / 파기(discard)' 5개입니다.
- 각 단계는 배열이며, 배열 원소 하나가 흐름표의 한 줄(row)에 해당합니다.
- 모르는 값은 빈 문자열 ""로 두되, 거짓인 값은 false, 참인 값은 true 로 명시합니다.
- 논리적으로 말이 되도록 추론하되, 과도한 추측은 피하고 문서에서 근거를 찾으려 하십시오.

JSON 필드 스키마는 다음과 같습니다. 필드명은 반드시 그대로 사용하십시오.

{
  "collect": [
    {
      "collect_task": "string",         // 수집 업무명
      "collect_target": "string",       // 수집 대상(민원인, 고객 등)
      "collect_route": "string",        // 수집 경로(인터넷, 방문, 전화 등)
      "collect_dept": "string",         // 담당 부서
      "collect_purpose": "string",      // 수집 목적
      "collect_system": "string",       // 수집에 사용하는 시스템/화면
      "collect_space": "string",        // 수집 후 저장 공간(DB, 서류함 등) - 있으면
      "collect_bundle": "string",       // 묶음명, 그룹명
      "collect_items": "string",        // 수집하는 개인정보 항목 전체를 쉼표로 나열
      "collect_online": true,
      "collect_encrypt": true
    }
  ],
  "retain": [
    {
      "retain_task": "string",
      "retain_input_system": "string",
      "retain_space": "string",
      "retain_form": "string",
      "retain_purpose": "string",
      "retain_bundle": "string",
      "retain_items": "string",
      "retain_online": true,
      "retain_encrypt": true,
      "retain_enc_items": "string"
    }
  ],
  "use": [
    {
      "use_task": "string",
      "use_space": "string",
      "use_system": "string",
      "use_dept": "string",
      "use_purpose": "string",
      "use_method": "string",
      "use_bundle": "string",
      "use_items": "string",
      "use_online": true,
      "use_encrypt": true
    }
  ],
  "provide": [
    {
      "provide_task": "string",
      "provide_space": "string",
      "provide_dept": "string",
      "provide_system": "string",
      "provide_sys_online": true,
      "provide_sys_encrypt": true,
      "receiver": "string",
      "provide_bundle": "string",
      "provide_items": "string",
      "provide_purpose": "string",
      "provide_method": "string",
      "receiver_online": true,
      "receiver_encrypt": true
    }
  ],
  "discard": [
    {
      "discard_task": "string",
      "discard_space": "string",
      "discard_system": "string",
      "discard_period": "string",
      "discard_dept": "string",
      "discard_proc": "string",
      "discard_bundle": "string",
      "discard_items": "string",
      "discard_online": true,
      "discard_encrypt": true
    }
  ]
}

반드시 위와 같은 top-level 키를 가진 단일 JSON 객체만 출력하십시오.
추가적인 설명 문장이나 마크다운을 출력하지 마십시오.
"""

async def generate_flow_sheets_from_text(
    plain_text: str,
    company_id: str | None = None,
    task_id: str | None = None,
) -> Dict[str, Any]:
    """
    문서 텍스트를 받아 Azure OpenAI로부터 흐름표 초안을 생성하는 함수.
    반환값은 Python dict (collect/retain/use/provide/discard 구조).
    """

    if client is None:
        # 이때 비로소 에러 발생 → 서버는 뜨고, AI API 호출할 때만 500
        raise RuntimeError("Azure OpenAI 환경변수(AZURE_OPENAI_*)가 설정되지 않았습니다.")

    # company_id, task_id를 프롬프트에 넣고 싶으면 meta 로 사용
    extra_context: Dict[str, Any] = {}
    if company_id:
        extra_context["company_id"] = company_id
    if task_id:
        extra_context["task_id"] = task_id

    user_prompt = "다음은 특정 업무에 대한 설명입니다. 이 내용을 기준으로 개인정보 흐름표를 생성하세요.\n\n"

    if extra_context:
        meta_str = "\n".join(f"- {k}: {v}" for k, v in extra_context.items())
        user_prompt += f"[업무 메타데이터]\n{meta_str}\n\n"

    user_prompt += "[업무 설명]\n" + plain_text

    # Azure OpenAI 호출 (동기지만, 일단 그대로 사용)
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Azure OpenAI JSON 파싱 실패: {e} / raw={content[:200]}")

    return data