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
당신은 개인정보 영향평가(PIA) 분석 전문가이자 비서입니다.
입력으로 한국어 설명 문서(대화체, 비정형 텍스트, 오타 포함 가능)를 받으면,
해당 시스템/업무의 개인정보 처리 흐름을 아래 JSON 스키마에 정확하게 채워야 합니다.

========================
전반적 규칙
========================
1. 흐름 단계는 반드시 5개: 
   collect / retain / use / provide / discard

2. 각 단계를 배열로 구성하며, 
   배열의 각 원소는 "한 개의 업무 프로세스를 표현하는 하나의 row"이다.

3. 문서에 명시된 내용만 사용하되,
   - "명시 + 강한 논리적 추론"만 허용
   - 근거가 불확실하거나 추측성인 경우 절대 채우지 말고 "" 로 둔다.

4. Boolean 값:
   - True/False 중 하나를 반드시 사용
   - 모르면 ""가 아니라 false도 아니다 → 반드시 ""가 아니라 True/False 중 선택해야 하는 필드만 True/False
   - 모를 경우: 일관성 원칙 따라 보수적으로 판단
     (예: 온라인 여부 모르면 false, 암호화 여부 모르면 false)

5. 개인정보 항목은 쉼표(,)로 구분하여 하나의 문자열로 작성한다.  
   예: "성명, 주소, 연락처, 이메일"

6. 묶음명(bundle)은 "해당 개인정보 항목을 화면/양식 단위로 묶어 부르는 이름"이다.  
   예: "민원 정보", "신청서 정보"

7. 어떤 필드가 문서에 전혀 언급되지 않으면 반드시 빈 문자열 "" 로 둔다.

8. 절대로 JSON 외의 문장, 설명, 마크다운을 출력하지 않는다.
   → 오직 단일 JSON 객체만 출력한다.

========================
단계별 필드 해석 규칙
========================

------------------------------------
1) 수집 영역(collect)
------------------------------------
각 row는 “개인정보가 최초로 시스템에 유입되는 순간”을 의미한다.
다음 기준을 따른다:

- collect_task:  
  수집 업무명 또는 수집 단계의 프로세스 이름  
  (예: "인터넷 민원 접수", "방문 신청서 접수")

- collect_target:  
  개인정보를 제공하는 정보주체 종류  
  (예: "민원인", "고객", "직원")

- collect_route:  
  개인정보가 들어온 경로  
  (예: "인터넷", "방문", "전화", "우편")

- collect_dept:  
  해당 개인정보를 수집하는 부서/담당자  
  (예: "민원접수담당자")

- collect_purpose:  
  개인정보를 수집하는 목적  
  (예: "민원 접수")

- collect_system:  
  입력에 사용된 시스템/화면/매체  
  (예: "인터넷 민원시스템(민원 접수 화면)", "창구 PC")

- collect_space:  
  수집 직후 저장되는 공간 또는 중간 저장처  
  (명시된 경우에만 입력: DB명, 저장소명 등)

- collect_bundle:  
  수집 항목을 묶어 부르는 이름  
  (예: "민원 정보", "고객 정보")

- collect_items:  
  수집되는 개인정보 항목 전체  
  (예: "성명, 주소, 연락처, 이메일, 주민등록번호, 민원내용")

- collect_online:  
  온라인 수집 여부(True/False)

- collect_encrypt:  
  저장 시 또는 전송 시 암호화 여부(True/False)


------------------------------------
2) 보유 영역(retain)
------------------------------------
개인정보를 저장/보관하고 있는 상태를 하나의 row로 표현한다.

- retain_task:  
  보유 업무명 또는 보관 프로세스 이름

- retain_input_system:  
  해당 정보가 입력/저장된 시스템 또는 매체

- retain_space:  
  개인정보가 실제로 보관되는 물리/논리적 위치  
  (예: "민원 DB", "서류 보관함")

- retain_form:  
  보유 형태 (예: "엑셀파일", "텍스트", "A4 서류")

- retain_purpose:  
  개인정보를 보관하는 목적

- retain_bundle:  
  항목군 묶음명(화면/양식 단위)

- retain_items:  
  보유하고 있는 개인정보 항목 전체

- retain_online:  
  온라인 보유 여부(True/False)

- retain_encrypt:  
  저장된 정보의 암호화 여부(True/False)

- retain_enc_items:  
  암호화된 개인정보 항목(명시된 경우만 기록, 일반 암호화 시 “( )” 표기 규칙은 무시하고 문자열만 입력)


------------------------------------
3) 이용 영역(use)
------------------------------------
개인정보가 실제로 조회·검색·처리되는 과정.

- use_task: 이용 업무명
- use_space: 이용 시 참조하는 DB 또는 보관 위치
- use_system: 조회/검색/처리에 사용되는 시스템
- use_dept: 이용하는 부서 또는 사용자 역할
- use_purpose: 이용 목적
- use_method: 이용자가 이용하는 방식  
  (예: "조회", "검색", "다운로드")
- use_bundle: 이용 항목 묶음명
- use_items: 이용하는 개인정보 항목
- use_online: 온라인으로 이용하는지 여부(True/False)
- use_encrypt: 이용 과정에서 암호화 여부(True/False)


------------------------------------
4) 제공 영역(provide)
------------------------------------
개인정보를 제3자에게 보내는 단계.

- provide_task: 제공 업무명
- provide_space: 제공 정보가 적재된 공간
- provide_dept: 제공을 수행하는 부서/담당자
- provide_system: 연계 시스템/제공 시스템
- provide_sys_online: 연계 시스템의 온라인 여부(True/False)
- provide_sys_encrypt: 연계 시스템 이동 시 암호화 여부(True/False)
- receiver: 정보 수신자(기관명, 업체명)
- provide_bundle: 제공 항목 묶음명
- provide_items: 제공되는 개인정보 항목
- provide_purpose: 제공 목적
- provide_method: 제공 방식  
  (예: "EAI", "FTP", "API", "이메일")
- receiver_online: 수신자의 수신 시스템이 온라인인지 여부
- receiver_encrypt: 수신 단계에서 암호화되는지 여부


------------------------------------
5) 파기 영역(discard)
------------------------------------
정보가 삭제되거나 파쇄되는 단계.

- discard_task: 파기 업무명
- discard_space: 파기 대상 정보가 보관된 장소
- discard_system: 파기 시스템(배치 프로그램/파쇄기 등)
- discard_period: 보관 기간 또는 파기 시점
- discard_dept: 파기를 수행하는 부서
- discard_proc: 파기 절차(예: "보존 DB 이동 후 자동 파기", "연 1회 파쇄")
- discard_bundle: 파기되는 개인정보 묶음명
- discard_items: 파기되는 개인정보 항목
- discard_online: 파기 시스템의 온라인 여부(True/False)
- discard_encrypt: 파기 과정에서 암호화 여부(True/False)

========================
출력 규칙
========================
반드시 아래 구조의 **단일 JSON 객체만 출력**해야 한다:

{
  "collect": [...],
  "retain": [...],
  "use": [...],
  "provide": [...],
  "discard": [...]
}

JSON 외의 어떤 문장/설명/마크다운도 출력하지 말 것.

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