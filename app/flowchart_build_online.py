# -*- coding: utf-8 -*-
import os, json, math, re, sys
from collections import OrderedDict, defaultdict
from typing import Dict, Any, List, Optional

# ===== (옵션) 로컬 엑셀 테스트용 =====
try:
    import pandas as pd
except Exception:
    pd = None

# ===== Paths (로컬 테스트) =====
SRC_XLSX = "./flowchart.xlsx"
OUT_DIR = "./"
OUT_JSON = os.path.join(OUT_DIR, "combined.json")

VERBOSE = True
def log(msg):
    if VERBOSE:
        print(msg)
# -------------------------------------------------
# 공통 유틸
# -------------------------------------------------

def norm(s):
    """정규화: 공백 제거 + 소문자. None/NaN도 빈문자."""
    if s is None:
        return ""
    if isinstance(s, float) and math.isnan(s):
        return ""
    return re.sub(r"\s+", "", str(s)).casefold()

def text_keep(s):
    """사람이 읽는 텍스트 그대로(양쪽 공백만 trim). NaN은 ''."""
    if s is None:
        return ""
    return str(s).strip()

def num_to_circle(n: int) -> str:
    # ①(1)~⑳(20)
    if 1 <= n <= 20:
        return chr(0x2460 + (n - 1))
    # ㉑(21)~㉟(35)
    if 21 <= n <= 35:
        return chr(0x3251 + (n - 21))
    # ㊱(36)~㊿(50)
    if 36 <= n <= 50:
        return chr(0x32B1 + (n - 36))
    # 범위를 넘으면 그냥 숫자 문자열 유지
    return str(n)

def split_fields(fields_text: str) -> List[str]:
    raw = text_keep(fields_text)
    if not raw:
        return []
    parts = re.split(r"[,;\n]+", raw)
    return [p.strip() for p in parts if p.strip()]

# -------------------------------------------------
# PII
# -------------------------------------------------
class PiiRegistry:
    def __init__(self):
        self.registry = OrderedDict()
        self.next_idx = 1

    def get_idx_and_update(self, bundle_name: Optional[str], fields_text: Optional[str]):
        bname = text_keep(bundle_name)
        if not bname:
            return None
        nkey = norm(bname)
        if nkey not in self.registry:
            self.registry[nkey] = {
                "id": bname,
                "idx": self.next_idx,
                "fields": OrderedDict()
            }
            self.next_idx += 1
        obj = self.registry[nkey]
        for f in split_fields(fields_text or ""):
            obj["fields"][f] = True
        return obj["idx"]

    def export_list(self):
        out = []
        for _, obj in self.registry.items():
            out.append({
                "idx": obj["idx"],
                "id":  obj["id"],
                "fields": list(obj["fields"].keys())
            })
        out.sort(key=lambda x: x["idx"])
        return out

# -------------------------------------------------
# Description
# -------------------------------------------------
class DescriptionBuilder:
    def __init__(self):
        self.data = {
            "수집": OrderedDict(), "보유": OrderedDict(),
            "이용": OrderedDict(), "제공": OrderedDict(),
            "파기": OrderedDict(),
        }
    def add(self, phase, entity_type, entity_name, task_name, details_dict):
        if not entity_type or not entity_name or not task_name:
            return
        od = self.data[phase]
        k = (entity_type, entity_name)
        if k not in od:
            od[k] = {
                "entity_type": entity_type,
                "entity_name": entity_name,
                "tasks": []
            }
        clean = {k: text_keep(v) for k, v in (details_dict or {}).items() if text_keep(v) != ""}
        od[k]["tasks"].append({"task_name": text_keep(task_name), "details": clean})

    def export(self):
        return {phase: list(od.values()) for phase, od in self.data.items()}

def pack_description_text(desc_dict: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for phase, entities in desc_dict.items():
        lines = []
        for ent in entities or []:
            name = text_keep(ent.get("entity_name"))
            if not name:
                continue
            lines.append(f"■ {name}")
            for t in (ent.get("tasks") or []):
                tname = text_keep(t.get("task_name"))
                if tname:
                    lines.append(f"- {tname}")
                det = t.get("details") or {}
                for k, v in det.items():
                    vv = text_keep(v)
                    if vv != "":
                        lines.append(f"· {k}: {vv}")
            lines.append("")
        out[phase] = "\n".join(lines).strip()
    return out

# -------------------------------------------------
# 노드 / 링크 관리
# -------------------------------------------------
NODE_META = {}  # key -> {"col": int, "row": int}

def wrap_name(name, width=11):
    name = str(name)
    if len(name) <= width:
        return name
    return "\n".join(name[i:i+width] for i in range(0, len(name), width))

def unique_push_node(registry, nodeDataArray, display_text, category, col_idx, y_slot, key_counter, online_flag=None):
    nkey = norm(display_text)
    if not nkey:
        return None
    if nkey in registry:
        node_info = registry[nkey]
        if online_flag is not None and node_info["online"] is not True:
            node_info["online"] = bool(online_flag)
        return node_info["key"]
    key = key_counter[0]; key_counter[0] += 1
    x_gap = 210; left_offset = 30
    x = left_offset + col_idx * x_gap
    y = 10 + y_slot * 120
    node_obj = {
        "key": key, "text": wrap_name(display_text), "category": category,
        "loc": f"{x} {y}", "online": (True if online_flag else False) if online_flag is not None else None
    }
    nodeDataArray.append(node_obj)
    registry[nkey] = {"key": key, "online": node_obj["online"]}
    NODE_META[key] = {"col": col_idx, "row": y_slot}
    return key

def push_link(linkDataArray, from_key, to_key, label_text=None, is_online=True, is_encrypted=False):
    if from_key is None or to_key is None:
        return
    obj = {"from": from_key, "to": to_key, "category": ("solid" if is_online else "dashed")}
    if label_text:
        obj["text"] = label_text
    if is_encrypted:
        obj["stroke"] = "red"
    linkDataArray.append(obj)

# -------------------------------------------------
# 온라인 경로: DB sheets -> derived
# -------------------------------------------------
def build_from_sheets(sheets: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """
    sheets = {
      "collect":[{...}], "retain":[...], "use":[...], "provide":[...], "discard":[...]
    }
    return combined = { diagram, pii, description }
    """
    # 누적 컨테이너
    nodeDataArray: List[Dict[str, Any]] = []
    linkDataArray: List[Dict[str, Any]] = []
    reg_default = {}; reg_database = {}; reg_recipient_use = {}; reg_recipient_provide = {}
    reg_system_collect = {}; reg_system_use = {}; reg_system_provide = {}; reg_system_discard = {}
    yslot = defaultdict(int); key_counter = [1]
    COLIDX = { "수집":0, "보유":1, "이용":2, "제공":3, "파기":4 }
    pii_reg = PiiRegistry()
    desc_builder = DescriptionBuilder()
    seen_provide_pair = set()

    # ---- 수집
    for r in sheets.get("collect", []):
        task    = text_keep(r.get("collect_task"))
        target  = text_keep(r.get("collect_target"))
        route   = text_keep(r.get("collect_route"))
        dept    = text_keep(r.get("collect_dept"))
        purpose = text_keep(r.get("collect_purpose"))
        system  = text_keep(r.get("collect_system"))
        bundle  = text_keep(r.get("collect_bundle"))
        items   = text_keep(r.get("collect_items"))
        online  = bool(r.get("collect_online"))
        enc     = bool(r.get("collect_encrypt"))
        if not any([task, target, system, bundle, items, route, dept, purpose]):
            continue

        row_base = yslot["수집"]; used = 0
        def _key(reg, name):
            n = norm(name); 
            if not n: return None
            ent = reg.get(n); 
            return ent["key"] if isinstance(ent, dict) else ent

        tkey = _key(reg_default, target) if target else None
        if target and not tkey:
            tkey = unique_push_node(reg_default, nodeDataArray, target, "subject",
                                    COLIDX["수집"], row_base+used, key_counter, online_flag=None); used += 1

        skey = _key(reg_system_collect, system) if system else None
        if system and not skey:
            skey = unique_push_node(reg_system_collect, nodeDataArray, system, "system",
                                    COLIDX["수집"], row_base+used, key_counter, online_flag=online); used += 1

        yslot["수집"] += used

        idx_num = pii_reg.get_idx_and_update(bundle, items)
        label_text = f"{idx_num}" if idx_num else None

        if tkey and skey:
            push_link(linkDataArray, tkey, skey, label_text, is_online=online, is_encrypted=enc)

        if target and task:
            desc_builder.add("수집","수집 대상",target,task,{
                "수집 시스템": system, "수집 경로": route, "수집 부서": dept, "수집 목적": purpose
            })

    # ---- 보유
    for r in sheets.get("retain", []):
        task   = text_keep(r.get("retain_task"))
        in_sys = text_keep(r.get("retain_input_system"))
        space  = text_keep(r.get("retain_space"))
        form   = text_keep(r.get("retain_form"))
        purpose= text_keep(r.get("retain_purpose"))
        bundle = text_keep(r.get("retain_bundle"))
        items  = text_keep(r.get("retain_items"))
        online = bool(r.get("retain_online"))
        enc    = bool(r.get("retain_encrypt"))
        enc_it = text_keep(r.get("retain_enc_items"))
        if not any([task, in_sys, space, bundle, items, form, purpose, enc_it]):
            continue

        dkey = None
        if space:
            prev = len(nodeDataArray)
            dkey = unique_push_node(reg_database, nodeDataArray, space, "database",
                                    COLIDX["보유"], yslot["보유"], key_counter, online_flag=online)
            if len(nodeDataArray) > prev: yslot["보유"] += 1

        skey = None
        if in_sys:
            n_in = norm(in_sys)
            if n_in in reg_system_collect:
                ent = reg_system_collect[n_in]
                skey = ent["key"] if isinstance(ent, dict) else ent
            else:
                prev2 = len(nodeDataArray)
                skey = unique_push_node(reg_system_collect, nodeDataArray, in_sys, "system",
                                        COLIDX["수집"], yslot["수집"], key_counter, online_flag=online)
                if len(nodeDataArray) > prev2: yslot["수집"] += 1

        idx_num = pii_reg.get_idx_and_update(bundle, items)
        label_text = f"{idx_num}" if idx_num else None

        if skey and dkey:
            push_link(linkDataArray, skey, dkey, label_text, is_online=online, is_encrypted=enc)

        if space and task:
            desc_builder.add("보유","보유 공간",space,task,{
                "보유 형태": form, "보유 목적": purpose, "암호화 항목": enc_it
            })

    # ---- 이용
    for r in sheets.get("use", []):
        task   = text_keep(r.get("use_task"))
        space  = text_keep(r.get("use_space"))
        system = text_keep(r.get("use_system"))
        dept   = text_keep(r.get("use_dept"))
        purpose= text_keep(r.get("use_purpose"))
        method = text_keep(r.get("use_method"))
        bundle = text_keep(r.get("use_bundle"))
        items  = text_keep(r.get("use_items"))
        online = bool(r.get("use_online"))
        enc    = bool(r.get("use_encrypt"))
        if not any([task, space, system, bundle, items, dept, purpose, method]):
            continue

        # 보유공간을 찾고, 없으면 보유공간 노드를 새로 생성
        dkey = None
        if space:
            nspace = norm(space)
            if nspace in reg_database:
                dkey = unique_push_node(
                    reg_database, nodeDataArray, space, "database",
                    COLIDX["보유"], yslot["보유"], key_counter, online_flag=None
                )
            else:
                dkey = unique_push_node(
                    reg_database, nodeDataArray, space, "database",
                    COLIDX["보유"], yslot["보유"], key_counter, online_flag=online
                )
                yslot["보유"] += 1

        # 이용 시스템(system)
        skey = None
        if system:
            prev_len = len(nodeDataArray)
            skey = unique_push_node(
                reg_system_use, nodeDataArray, system, "system",
                COLIDX["이용"], yslot["이용"], key_counter, online_flag=online
            )
            if len(nodeDataArray) > prev_len:                  # 새로 생성된 경우에만
                yslot["이용"] += 1

        # 이용자(recipient)
        rkey = None
        has_dept = bool(dept)
        if has_dept:
            prev_len = len(nodeDataArray)  
            rkey = unique_push_node(
                reg_recipient_use, nodeDataArray, dept, "recipient",
                COLIDX["이용"], yslot["이용"], key_counter, online_flag=online
            )
            if len(nodeDataArray) > prev_len:                  # 새로 생성된 경우에만
                yslot["이용"] += 1

        # PII 번호
        idx_num = pii_reg.get_idx_and_update(bundle, items)
        label_text = f"{idx_num}" if idx_num else None

        # 링크: 보유 → 이용 시스템 (부서가 있으면 텍스트 없음)
        if dkey and skey:
            push_link(
                linkDataArray, dkey, skey,
                None if has_dept else label_text,
                is_online=online, is_encrypted=enc
            )

        # 링크: (이용자가 있으면) 이용 시스템 → 이용자
        if has_dept and skey and rkey:
            push_link(
                linkDataArray, skey, rkey,
                label_text,
                is_online=online, is_encrypted=enc
            )

        # description
        if system and task:
            desc_builder.add(
                "이용", "이용 시스템", system, task,
                {"이용자": dept, "이용 목적": purpose, "이용 방법": method}
            )

    # ---- 제공
    for r in sheets.get("provide", []):
        task   = text_keep(r.get("provide_task"))
        space  = text_keep(r.get("provide_space"))
        dept   = text_keep(r.get("provide_dept"))
        psys   = text_keep(r.get("provide_system"))
        sys_on = bool(r.get("provide_sys_online"))
        sys_en = bool(r.get("provide_sys_encrypt"))
        recv   = text_keep(r.get("receiver"))
        bundle = text_keep(r.get("provide_bundle"))
        items  = text_keep(r.get("provide_items"))
        purpose= text_keep(r.get("provide_purpose"))
        method = text_keep(r.get("provide_method"))
        r_on   = bool(r.get("receiver_online"))
        r_en   = bool(r.get("receiver_encrypt"))
        if not any([task, space, psys, recv, bundle, items, dept, purpose, method]):
            continue

        # 보유공간을 찾고, 없으면 보유공간 노드를 새로 생성
        dkey = None
        if space:
            nspace = norm(space)
            if nspace in reg_database:
                dkey = unique_push_node(
                    reg_database, nodeDataArray, space, "database",
                    COLIDX["보유"], yslot["보유"], key_counter, online_flag=None
                )
            else:
                dkey = unique_push_node(
                    reg_database, nodeDataArray, space, "database",
                    COLIDX["보유"], yslot["보유"], key_counter, online_flag=sys_on
                )
                yslot["보유"] += 1

        # 연계 시스템 (system) — 제공 단계 전용
        pkey = None
        if psys:
            nsys = norm(psys)
            is_new_sys = nsys not in reg_system_provide
            pkey = unique_push_node(
                reg_system_provide, nodeDataArray, psys, "system",
                COLIDX["제공"], yslot["제공"], key_counter, online_flag=sys_on
            )
            if is_new_sys:
                yslot["제공"] += 1

        # 수신자 (recipient) — 전용 레지스트리 사용
        rkey = None
        if recv:
            nrecv = norm(recv)
            is_new_recv = nrecv not in reg_recipient_provide   # ★ reg_recipient_provide 사용
            rkey = unique_push_node(
                reg_recipient_provide, nodeDataArray, recv, "recipient",
                COLIDX["제공"], yslot["제공"], key_counter, online_flag=None
            )
            if is_new_recv:
                yslot["제공"] += 1

        # PII 번호
        idx_num = pii_reg.get_idx_and_update(bundle, items)
        label_text = f"{idx_num}" if idx_num else None

        # (1) [보유 공간] -> [연계 시스템]
        if dkey and pkey:
            pair = (dkey, pkey)
            if pair not in seen_provide_pair:
                seen_provide_pair.add(pair)
                push_link(linkDataArray, dkey, pkey, label_text, is_online=sys_on, is_encrypted=sys_en)

        # (2) [연계 시스템] -> [수신자]
        if pkey and rkey:
            push_link(linkDataArray, pkey, rkey, label_text, is_online=r_on, is_encrypted=r_en)

        # (3) 시스템이 없고 수신자만 있을 때: [보유] -> [수신자]
        if (pkey is None) and dkey and rkey:
            push_link(linkDataArray, dkey, rkey, label_text, is_online=r_on, is_encrypted=r_en)

        # description
        if recv and task:
            desc_builder.add("제공", "수신자", recv, task, {
                "제공 부서": dept, "제공 목적": purpose, "제공 방법": method
            })

    # ---- 파기
    for r in sheets.get("discard", []):
        task   = text_keep(r.get("discard_task"))
        space  = text_keep(r.get("discard_space"))
        dsys   = text_keep(r.get("discard_system"))
        period = text_keep(r.get("discard_period"))
        dept   = text_keep(r.get("discard_dept"))
        proc   = text_keep(r.get("discard_proc"))
        bundle = text_keep(r.get("discard_bundle"))
        items  = text_keep(r.get("discard_items"))
        d_on   = bool(r.get("discard_online"))

        if not any([task, space, dsys, bundle, items, period, dept, proc]):
            continue

        # 보유공간을 찾고, 없으면 보유공간 노드를 새로 생성
        dkey = None
        if space:
            nspace = norm(space)
            if nspace in reg_database:
                dkey = unique_push_node(reg_database, nodeDataArray, space, "database",
                                        COLIDX["보유"], yslot["보유"], key_counter, online_flag=None)
            else:
                dkey = unique_push_node(reg_database, nodeDataArray, space, "database",
                                        COLIDX["보유"], yslot["보유"], key_counter, online_flag=d_on)
                yslot["보유"] += 1

        # 파기 시스템 노드
        skey = None
        dsys_label = dsys if not period else f"{dsys}"
        if dsys_label:
            skey = unique_push_node(reg_system_discard, nodeDataArray, dsys_label, "discard",
                                    COLIDX["파기"], yslot["파기"], key_counter, online_flag=d_on)
            if skey is not None:
                yslot["파기"] += 1
                
        # pii 인덱스
        idx_num = pii_reg.get_idx_and_update(bundle, items)
        label_text = f"{idx_num}" if idx_num else None

        # 링크: (보유 공간 → 파기 시스템)
        if dkey and skey:
            push_link(linkDataArray, dkey, skey, label_text, is_online=d_on, is_encrypted=False)

        # 설명
        if dsys and task:
            desc_builder.add("파기", "파기 시스템", dsys, task, {
                "파기 부서": dept,
                "보관기간": period,
                "파기 절차": proc
            })

    # ---- 마무리: description/labels
    description_out = desc_builder.export()
    description_out_text = pack_description_text(description_out)
    pii_out = pii_reg.export_list()

    # 링크 라벨 원형 숫자 변환
    for ld in linkDataArray:
        txt = ld.get("text")
        if txt is None: 
            continue
        try:
            n = int(str(txt).strip())
            ld["text"] = num_to_circle(n)
        except Exception:
            pass

    diagram = {
        "class": "GraphLinksModel",
        "modelData": { "position": "-5 -5", "flowTitle": title or "" },
        "nodeDataArray": nodeDataArray,
        "linkDataArray": linkDataArray
    }
    combined = {
        "diagram": diagram,
        "pii": pii_out,
        "description": description_out_text,
        "concern": ""
    }
    return combined

# ==== (옵션) 로컬 엑셀 → combined.json ====
def build_local_from_excel() -> str:
    if pd is None:
        sys.exit("[ERROR] pandas가 없습니다. 온라인 경로만 사용하세요.")
    xls = pd.ExcelFile(SRC_XLSX)
    # (기존 오프라인 로직은 생략하거나 필요 시 여기에 넣으세요)
    # 대신: 실전은 build_from_sheets()를 쓰도록 권장
    combined = {"diagram": {"class":"GraphLinksModel","nodeDataArray":[],"linkDataArray":[]},
                "pii": [], "description": {"수집":"","보유":"","이용":"","제공":"","파기":""}}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    return OUT_JSON

if __name__ == "__main__":
    build_local_from_excel()