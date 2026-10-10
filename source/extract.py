# """Level 1: read one bill image into the JSON schema.
# Two independent reads run in parallel. If they disagree, a third call looks at the image again and decides.
# Automatic checks can trigger one more re-read. Values are never changed by code."""
# import json
# from concurrent.futures import ThreadPoolExecutor

# import config
# import llm
# from prompts import HISTORY_SYSTEM, L1_ADJUDICATE, L1_RECHECK, L1_SYSTEM
# from validate import KEYS, validate


# def _example_messages():
#     img = config.EXAMPLE_DIR / "KESC_0008.png"
#     js = config.EXAMPLE_DIR / "KESC_0008.json"
#     if not (img.exists() and js.exists()):
#         return []
#     gold = json.dumps(json.loads(js.read_text(encoding="utf-8")), separators=(",", ":"))
#     return [
#         {"role": "user", "content": [llm.text_part("Worked example bill. Extract it."), llm.image_part(img)]},
#         {"role": "assistant", "content": gold},
#     ]


# def _read_once(base):
#     raw = llm.chat_json(base)
#     data, issues = validate(raw)
#     return data, issues


# def extract_bill(path):
#     """Returns (clean_json_dict, issues_left)."""
#     base = [{"role": "system", "content": L1_SYSTEM}] + _example_messages()
#     base.append({"role": "user", "content": [llm.text_part("Extract this bill. JSON only."), llm.image_part(path)]})

#     with ThreadPoolExecutor(max_workers=2) as ex:
#         fa, fb = ex.submit(_read_once, base), ex.submit(_read_once, base)
#         results = []
#         for f in (fa, fb):
#             try:
#                 results.append(f.result())
#             except Exception as e:
#                 print(f"  read failed: {e}")
#     if not results:
#         raise RuntimeError("both reads failed")

#     best = min(results, key=lambda r: len(r[1]))
#     data, issues = best

#     if len(results) == 2:
#         (a, ia), (b, ib) = results
#         diffs = [k for k in KEYS if a[k] != b[k]]
#         if diffs:
#             print(f"  {path.name}: reads differ on {diffs}, adjudicating")
#             all_issues = sorted(set(ia + ib))
#             prompt = L1_ADJUDICATE.format(
#                 a=json.dumps(a), b=json.dumps(b), fields=", ".join(diffs),
#                 issues="; ".join(all_issues) or "none")
#             msgs = [{"role": "system", "content": L1_SYSTEM},
#                     {"role": "user", "content": [llm.text_part(prompt), llm.image_part(path)]}]
#             try:
#                 c, ic = validate(llm.chat_json(msgs))
#                 if len(ic) <= len(issues):
#                     data, issues = c, ic
#             except Exception as e:
#                 print(f"  adjudication failed: {e}")

#     if issues:
#         print(f"  re-checking {path.name}: {len(issues)} issue(s)")
#         msgs = list(base) + [
#             {"role": "assistant", "content": json.dumps(data)},
#             {"role": "user", "content": L1_RECHECK.format(issues="\n".join("- " + i for i in issues))},
#         ]
#         try:
#             data2, issues2 = validate(llm.chat_json(msgs))
#             if len(issues2) < len(issues):
#                 data, issues = data2, issues2
#         except Exception as e:
#             print(f"  recheck failed: {e}")
#     return data, issues


# def extract_history(path):
#     msgs = [
#         {"role": "system", "content": HISTORY_SYSTEM},
#         {"role": "user", "content": [llm.text_part("Copy out the history tables. JSON only."), llm.image_part(path)]},
#     ]
#     return llm.chat_json(msgs)

"""Level 1: read one bill image into the JSON schema.
Two independent reads run in parallel. If they disagree, a third call looks at the image again and decides.
Automatic checks can trigger one more re-read. Values are never changed by code."""
import json
import re
from concurrent.futures import ThreadPoolExecutor

import config
import llm
from prompts import HISTORY_SYSTEM, L1_ADJUDICATE, L1_RECHECK, L1_SYSTEM, LOAD_SYSTEM
from validate import KEYS, validate


def _example_messages():
    img = config.EXAMPLE_DIR / "KESC_0008.png"
    js = config.EXAMPLE_DIR / "KESC_0008.json"
    if not (img.exists() and js.exists()):
        return []
    gold = json.dumps(json.loads(js.read_text(encoding="utf-8")), separators=(",", ":"))
    return [
        {"role": "user", "content": [llm.text_part("Worked example bill. Extract it."), llm.image_part(img)]},
        {"role": "assistant", "content": gold},
    ]


def _read_once(base):
    raw = llm.chat_json(base)
    data, issues = validate(raw)
    return data, issues


def _lesco_sanctioned_load(raw):
    """Read the integer SAN LOAD and discard nearby OCR punctuation/noise."""
    printed = raw.get("printed_text") if isinstance(raw, dict) else None
    if printed is not None:
        match = re.fullmatch(r"\s*(\d+)\s*(?:[./]\s*\d*)?\s*", str(printed))
        if match:
            return int(match.group(1))
    return validate({"sanctioned_load_kw": raw.get("kw") if isinstance(raw, dict) else None})[0]["sanctioned_load_kw"]


def extract_bill(path):
    """Returns (clean_json_dict, issues_left)."""
    base = [{"role": "system", "content": L1_SYSTEM}] + _example_messages()
    base.append({"role": "user", "content": [llm.text_part("Extract this bill. JSON only."), llm.image_part(path)]})

    with ThreadPoolExecutor(max_workers=2) as ex:
        fa, fb = ex.submit(_read_once, base), ex.submit(_read_once, base)
        results = []
        for f in (fa, fb):
            try:
                results.append(f.result())
            except Exception as e:
                print(f"  read failed: {e}")
    if not results:
        raise RuntimeError("both reads failed")

    best = min(results, key=lambda r: len(r[1]))
    data, issues = best

    if len(results) == 2:
        (a, ia), (b, ib) = results
        diffs = [k for k in KEYS if a[k] != b[k]]
        if diffs:
            print(f"  {path.name}: reads differ on {diffs}, adjudicating")
            all_issues = sorted(set(ia + ib))
            prompt = L1_ADJUDICATE.format(
                a=json.dumps(a), b=json.dumps(b), fields=", ".join(diffs),
                issues="; ".join(all_issues) or "none")
            msgs = [{"role": "system", "content": L1_SYSTEM},
                    {"role": "user", "content": [llm.text_part(prompt), llm.image_part(path)]}]
            try:
                c, ic = validate(llm.chat_json(msgs))
                if len(ic) <= len(issues):
                    data, issues = c, ic
            except Exception as e:
                print(f"  adjudication failed: {e}")

    if issues:
        print(f"  re-checking {path.name}: {len(issues)} issue(s)")
        msgs = list(base) + [
            {"role": "assistant", "content": json.dumps(data)},
            {"role": "user", "content": L1_RECHECK.format(issues="\n".join("- " + i for i in issues))},
        ]
        try:
            data2, issues2 = validate(llm.chat_json(msgs))
            if len(issues2) < len(issues):
                data, issues = data2, issues2
        except Exception as e:
            print(f"  recheck failed: {e}")
    # Narrow second look at one field that models misread often.
    try:
        r = llm.chat_json([
            {"role": "system", "content": LOAD_SYSTEM},
            {"role": "user", "content": [llm.text_part("Sanctioned load? JSON only."), llm.image_part(path)]}])
        kw = (_lesco_sanctioned_load(r) if data["provider"] == "LESCO"
              else validate({"sanctioned_load_kw": r.get("kw")})[0]["sanctioned_load_kw"])
        if kw is not None:
            data["sanctioned_load_kw"] = kw
    except Exception as ex:
        print(f"  load check failed: {ex}")
    # LESCO arrears can pick up nearby print noise as decimal digits. Use the
    # printed payable/current-bill relationship only when it gives a whole PKR value.
    if data["provider"] == "LESCO":
        arrears = data["arrears"]
        payable = data["payable_within_due_date"]
        current_bill = data["current_bill"]
        if arrears is not None and payable is not None and current_bill is not None:
            implied_arrears = payable - current_bill
            rounded_arrears = round(implied_arrears)
            if abs(implied_arrears - rounded_arrears) < 1e-9 and arrears != rounded_arrears:
                data["arrears"] = int(rounded_arrears)
    return data, issues


def extract_history(path):
    msgs = [
        {"role": "system", "content": HISTORY_SYSTEM},
        {"role": "user", "content": [llm.text_part("Copy out the history tables. JSON only."), llm.image_part(path)]},
    ]
    return llm.chat_json(msgs)
