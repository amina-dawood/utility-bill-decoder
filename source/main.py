"""Utility Bill Decoder: reads bill images, writes level1.csv and level2.csv.

Test run:  python main.py --bills ../data/test/bills --csv ../data/test/csv --out ../output
Dev run:   python main.py --bills ../data/train/bills --out ../output_dev --dev
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config
import csv_io
from extract import extract_bill, extract_history
from qa import answer_questions

EXTS = (".png", ".jpg", ".jpeg", ".webp")


def find_image(bills_dir, bill_id):
    for ext in EXTS:
        for cand in (bills_dir / f"{bill_id}{ext}", bills_dir / f"{bill_id}{ext.upper()}"):
            if cand.exists():
                return cand
    return None


def process_bill(bill_id, bills_dir, questions):
    print(f"[{bill_id}] start")
    path = find_image(bills_dir, bill_id)
    if path is None:
        print(f"[{bill_id}] image not found")
        return None, {qid: "Error" for qid, _ in questions}
    try:
        data, issues = extract_bill(path)
        if issues:
            print(f"[{bill_id}] remaining flags: {issues}")
    except Exception as e:
        print(f"[{bill_id}] Level 1 failed: {e}")
        return None, {qid: "Error" for qid, _ in questions}
    try:
        history = extract_history(path)
    except Exception as e:
        print(f"[{bill_id}] history failed: {e}")
        history = {}
    month_count = len(history.get("usage_history") or []) if isinstance(history, dict) else 0
    print(f"[{bill_id}] history months read: {month_count}")
    try:
        answers = answer_questions(path, data, history, questions)
    except Exception as e:
        print(f"[{bill_id}] Level 2 failed: {e}")
        answers = {qid: "Error" for qid, _ in questions}
    print(f"[{bill_id}] done")
    return data, answers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bills", default=str(config.BASE.parent / "data/test/bills"))
    ap.add_argument("--csv", default=str(config.BASE.parent / "data/test/csv"))
    ap.add_argument("--out", default=str(config.BASE.parent / "output"))
    ap.add_argument("--dev", action="store_true", help="no templates: build rows from the image folder")
    args = ap.parse_args()
    bills_dir, csv_dir, out_dir = Path(args.bills), Path(args.csv), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dev:
        ids = sorted(p.stem for p in bills_dir.iterdir() if p.suffix.lower() in EXTS)
        l1_rows = [{"bill_id": b, "json": ""} for b in ids]
        l2_rows = [{"bill_id": b, "question_id": qid, "question": q, "answer": ""}
                   for b in ids for qid, q in config.DEV_QUESTIONS]
        l1_fields = ["bill_id", "json"]
        l2_fields = ["bill_id", "question_id", "question", "answer"]
    else:
        l1_rows, l1_fields = csv_io.read_rows(csv_dir / "level1.csv")
        l2_rows, l2_fields = csv_io.read_rows(csv_dir / "level2.csv")

    questions_by_bill = {}
    for r in l2_rows:
        questions_by_bill.setdefault(r["bill_id"], []).append((r["question_id"], r["question"]))
    ids = [r["bill_id"] for r in l1_rows]
    print(f"{len(ids)} bills, model {config.MODEL_NAME}")

    with ThreadPoolExecutor(max_workers=config.WORKERS) as ex:
        futures = {b: ex.submit(process_bill, b, bills_dir, questions_by_bill.get(b, [])) for b in ids}
        results = {}
        for bill_id, future in futures.items():
            try:
                results[bill_id] = future.result()
            except Exception as e:
                print(f"[{bill_id}] processing failed: {e}")
                results[bill_id] = (None, {
                    qid: "Error" for qid, _ in questions_by_bill.get(bill_id, [])
                })

    for r in l1_rows:
        data = results[r["bill_id"]][0]
        r["json"] = csv_io.to_json_line(data) if data is not None else "null"
    for r in l2_rows:
        r["answer"] = results[r["bill_id"]][1].get(r["question_id"], "Error")

    csv_io.write_rows(out_dir / "level1.csv", l1_fields, l1_rows)
    csv_io.write_rows(out_dir / "level2.csv", l2_fields, l2_rows)
    print(f"Wrote {len(l1_rows)} rows to level1.csv and {len(l2_rows)} rows to level2.csv in {out_dir}")


if __name__ == "__main__":
    sys.exit(main())
