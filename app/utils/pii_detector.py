# app/utils/pii_detector.py
import re
from typing import Dict, List

def _norm(s: str) -> str:
    if not s:
        return ""
    # 공백/탭/개행 제거 + 소문자
    return re.sub(r"\s+", "", str(s)).casefold()

KEYWORDS = {
    # 고유식별정보
    "unique_id": [
        "주민등록번호", "주민번호",
        "여권번호", "여권",
        "운전면허번호", "운전면허",
        "외국인등록번호", "외국인등록",
    ],
    # 인증정보
    "auth": [
        "비밀번호", "패스워드", "password", "pw",
        "생체인식", "지문", "홍채", "정맥", "유전자",
    ],
    # 신용/금융정보
    "finance": [
        "신용카드번호", "신용카드 번호", "신용카드",
        "카드번호", "계좌번호", "계좌 번호", "계좌",
    ],
    # 의료정보
    "medical": [
        "건강상태", "진료기록", "병력", "의료정보",
    ],
    # 위치정보
    "location": [
        "개인위치정보", "위치정보", "gps", "위치",
    ],
    # 민감정보
    "sensitive": [
        "노동조합", "정당", "정치적", "성적", "장애", "종교",
    ],
}

def detect_sensitive_pii(text: str) -> Dict[str, bool]:
    t = _norm(text)

    out = {}
    for cat, kws in KEYWORDS.items():
        out[cat] = any(_norm(k) in t for k in kws)

    return out
