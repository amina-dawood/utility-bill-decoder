"""Level 2: answer the 12 questions for one bill. Arithmetic is done in Python, not by the model."""
import ast
import json
import operator
import re

import llm
from prompts import L2_SYSTEM

FALLBACK = "The bill could not be read reliably enough to answer this question."

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {
    "round": round, "sum": sum, "max": max, "min": min, "abs": abs, "len": len,
    "avg": lambda xs: sum(xs) / len(xs),
    "count_gt": lambda xs, n: sum(1 for x in xs if x > n),
    "count_lt": lambda xs, n: sum(1 for x in xs if x < n),
    "pct": lambda a, b: a / b * 100,
}


def _ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return n.value
    if isinstance(n, (ast.List, ast.Tuple)):
        return [_ev(e) for e in n.elts]
    if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
        return _OPS[type(n.op)](_ev(n.left), _ev(n.right))
    if isinstance(n, ast.UnaryOp) and type(n.op) in _UNARY:
        return _UNARY[type(n.op)](_ev(n.operand))
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
        return _FUNCS[n.func.id](*[_ev(a) for a in n.args])
    raise ValueError("unsupported expression")


def _fmt(v, spec):
    if spec:
        return format(round(v) if spec.endswith("d") else v, spec)
    return f"{int(round(v)):,}" if abs(v - round(v)) < 1e-9 else f"{v:,.2f}"


def _calc(match):
    inner = match.group(1).strip()
    m = re.match(r"^(.*?):([,.\d]*[fd%]?)$", inner, re.S)
    expr, spec = (m.group(1), m.group(2)) if m else (inner, "")
    try:
        return _fmt(_ev(ast.parse(expr.strip(), mode="eval").body), spec)
    except Exception:
        return expr.strip()


def fill_calcs(text):
    return re.sub(r"\{\{(.+?)\}\}", _calc, text, flags=re.S)


def derived_figures(b, h):
    """Numbers computed in Python from the extracted data, so the model can quote them."""
    f = {}
    tt, cb, u = b.get("total_taxes"), b.get("current_bill"), b.get("units_consumed")
    w, a = b.get("payable_within_due_date"), b.get("payable_after_due_date")
    if tt is not None and cb:
        f["taxes_as_percent_of_current_bill"] = round(tt / cb * 100, 2)
    if cb is not None and u:
        f["current_bill_per_unit"] = round(cb / u, 2)
    if w is not None and a is not None:
        f["extra_cost_if_paid_after_due_date"] = round(a - w, 2)
    rows = [m for m in (h.get("usage_history") or []) if isinstance(m, dict)
            and isinstance(m.get("units"), (int, float)) and not isinstance(m.get("units"), bool)]
    if rows:
        vals = [m["units"] for m in rows]
        hi = max(rows, key=lambda m: m["units"])
        lo = min(rows, key=lambda m: m["units"])
        f["history_month_count"] = len(rows)
        f["history_average_units"] = round(sum(vals) / len(vals), 1)
        f["history_highest"] = {"month": hi.get("month"), "units": hi["units"]}
        f["history_lowest"] = {"month": lo.get("month"), "units": lo["units"]}
    return f


def answer_questions(path, bill_json, history, questions):
    """questions: list of (question_id, question_text). Returns {question_id: answer}."""
    q_text = "\n".join(f"{qid}: {q}" for qid, q in questions)
    note = "" if (history or {}).get("usage_history") else (
        "NOTE: the usage history could not be read. If a question needs it, say the history is not available. Do not answer 0.\n\n")
    prompt = (f"Bill data (JSON):\n{json.dumps(bill_json)}\n\n"
              f"History tables (JSON):\n{json.dumps(history)}\n\n"
              f"Verified figures calculated by code (quote these exactly):\n{json.dumps(derived_figures(bill_json, history or {}))}\n\n"
              f"{note}"
              f"Questions:\n{q_text}\n\nAnswer all questions. JSON only.")
    msgs = [{"role": "system", "content": L2_SYSTEM},
            {"role": "user", "content": [llm.text_part(prompt), llm.image_part(path)]}]
    try:
        raw = llm.chat_json(msgs)
    except Exception as e:
        print(f"  Level 2 failed for {path.name}: {e}")
        raw = {}
    out = {}
    for qid, _ in questions:
        a = raw.get(qid) if isinstance(raw, dict) else None
        a = fill_calcs(str(a)).strip() if a else ""
        out[qid] = a or FALLBACK
    return out
