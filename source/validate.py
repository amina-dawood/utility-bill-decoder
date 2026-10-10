"""Clean model output into the exact Level 1 schema and run consistency checks.
Checks only flag problems (to trigger a re-read); they never change bill values."""
import re

KEYS = ["provider", "tariff", "sanctioned_load_kw", "bill_month", "reading_date", "issue_date",
        "due_date", "previous_reading", "current_reading", "units_consumed", "charges",
        "total_charges", "taxes", "total_taxes", "current_bill", "arrears",
        "payable_within_due_date", "payable_after_due_date"]
CHARGE_TYPES = {"energy", "fixed", "fpa", "quarterly_adjustment", "surcharge", "meter_rent", "subsidy", "other"}
TAX_TYPES = {"gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax"}
IMPORTANT = ["provider", "tariff", "bill_month", "due_date", "units_consumed", "current_bill",
             "payable_within_due_date"]


def empty_result():
    d = {k: None for k in KEYS}
    d["charges"], d["taxes"] = [], []
    return d


def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
    else:
        s = str(v).strip()
        if not s or s.lower() in {"null", "none", "n/a", "-"}:
            return None
        neg = bool(re.search(r"(CR|\bcredit\b)\s*$", s, re.I)) or s.startswith("(") or s.endswith("-")
        s = re.sub(r"(?i)rs\.?|pkr|cr\b|credit", "", s)
        s = re.sub(r"[,\s()]", "", s)
        s = s.strip("-") if neg and s.endswith("-") else s
        try:
            x = float(s)
        except ValueError:
            return None
        if neg and x > 0:
            x = -x
    x = round(x, 2)
    return int(x) if x == int(x) else x


def _date(v):
    if v is None:
        return None
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$", str(v))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _month(v):
    if v is None:
        return None
    m = re.match(r"^\s*(\d{4})-(\d{2})", str(v))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _provider(v):
    if v is None:
        return None
    s = re.sub(r"[^A-Z]", "", str(v).upper())
    if s in {"KE", "KESC", "KELECTRIC", "KELECTRICLIMITED"}:
        return "KE"
    if "LESCO" in s:
        return "LESCO"
    if "IESCO" in s:
        return "IESCO"
    return None


def _entries(items, allowed, default):
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        amt = num(it.get("amount"))
        if amt is None or amt == 0:
            continue
        t = str(it.get("type", "")).strip().lower()
        t = t if t in allowed else default
        if t == "subsidy" and amt > 0:
            amt = -amt
        out.append({"type": t, "amount": amt})
    return out


def _drop_subtotal_line(entries, total):
    """If the model listed the printed subtotal as an entry, remove that one entry."""
    if total is None or len(entries) < 2:
        return entries
    full = sum(x["amount"] for x in entries)
    for i, e in enumerate(entries):
        if e["amount"] == total:
            rest = full - e["amount"]
            if abs(rest - total) < abs(full - total):
                return entries[:i] + entries[i + 1:]
    return entries


def clean(raw):
    d = empty_result()
    if not isinstance(raw, dict):
        return d
    d["provider"] = _provider(raw.get("provider"))
    d["tariff"] = str(raw["tariff"]).strip() if raw.get("tariff") not in (None, "") else None
    d["bill_month"] = _month(raw.get("bill_month"))
    for k in ("reading_date", "issue_date", "due_date"):
        d[k] = _date(raw.get(k))
    for k in ("sanctioned_load_kw", "previous_reading", "current_reading", "units_consumed",
              "total_charges", "total_taxes", "current_bill", "arrears",
              "payable_within_due_date", "payable_after_due_date"):
        d[k] = num(raw.get(k))
    d["charges"] = _entries(raw.get("charges"), CHARGE_TYPES, "other")
    d["taxes"] = _entries(raw.get("taxes"), TAX_TYPES, "other_tax")
    d["charges"] = _drop_subtotal_line(d["charges"], d["total_charges"])
    d["taxes"] = _drop_subtotal_line(d["taxes"], d["total_taxes"])
    return d


def check(d):
    issues = []
    for k in IMPORTANT:
        if d[k] is None:
            issues.append(f"{k} is null. Check whether it is really missing or covered on the bill.")
    p, c, u = d["previous_reading"], d["current_reading"], d["units_consumed"]
    if None not in (p, c, u) and abs((c - p) - u) > 1:
        issues.append(f"current_reading - previous_reading = {c - p} but units_consumed = {u}.")
    if d["charges"] and d["total_charges"] is not None:
        s = sum(x["amount"] for x in d["charges"])
        if abs(s - d["total_charges"]) > 2:
            issues.append(f"charges add up to {round(s, 2)} but total_charges = {d['total_charges']}.")
    if d["taxes"] and d["total_taxes"] is not None:
        s = sum(x["amount"] for x in d["taxes"])
        if abs(s - d["total_taxes"]) > 2:
            issues.append(f"taxes add up to {round(s, 2)} but total_taxes = {d['total_taxes']}.")
    tc, tt, cb = d["total_charges"], d["total_taxes"], d["current_bill"]
    if None not in (tc, tt, cb) and abs(tc + tt - cb) > 2:
        issues.append(f"total_charges + total_taxes = {round(tc + tt, 2)} but current_bill = {cb}. "
                      "Check that total_charges is the printed charges subtotal (not a gross, net, grand total or current bill figure).")
    a, b = d["payable_within_due_date"], d["payable_after_due_date"]
    if None not in (a, b) and b < a:
        issues.append("payable_after_due_date is lower than payable_within_due_date.")
    return issues


def validate(raw):
    d = clean(raw)
    return d, check(d)
