#!/usr/bin/env python3
"""Project the saved aggregate results into readable tables.

Input:  results/primary_results.json -- public projection of the saved output of run
        DREC01_CORE_VALIDATION_PUBLIC_ALIAS_PILOT (a public alias); saved values unchanged (SHA-256 pinned below).
Output: results/group_estimates.csv, results/participant_results.csv,
        results/decision_criteria.csv, and Markdown table blocks that are
        embedded in README.md and results/README.md.

Nothing is re-estimated. Every number is a field of the saved file, written
with Python's round-trip float representation in the CSV files and rounded
only in the Markdown tables. The only derived values are deterministic
applications of the fixed protocol rules to saved numbers (for example,
"J <= 0.20 and C >= 0.50" per participant, or "upper bound < 0.02"); each
derived flag or count is cross-checked against the corresponding saved field.

Usage (standard library only, Python 3.9+), from the repository root:
    python scripts/make_result_tables.py          # write CSV files, print Markdown blocks
    python scripts/make_result_tables.py --check  # verify files and embedded tables, write nothing
"""
import argparse
import csv
import hashlib
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "primary_results.json"
SOURCE_SHA256 = "3f8f341d4fb638a994e8a9a33af9767934fdc48a01e24a8bdd3020036d259184"
RUN_ID = "DREC01_CORE_VALIDATION_PUBLIC_ALIAS_PILOT"

# Fixed protocol thresholds, as stated in the run configuration (code/pilot/candidate/config/RUN_CONFIG_v1.json).
J_MAX = 0.20          # individual J <= 0.20; group J upper bound < 0.20
C_MIN = 0.50          # individual C >= 0.50; group C lower bound > 0.50
NI_MARGIN = 0.02      # non-inferiority: upper bound of T-H J difference < 0.02
REQUIRED_PEOPLE = 7   # individual rule must hold in >= 7 of 9 participants
ACTIVE_REQUIRED = 6   # >= 2/3 active non-fallback seeds in >= 6 of 9 participants


def pointer(obj, ptr):
    """Resolve a JSON pointer such as /primary/delta/upper."""
    cur = obj
    for part in ptr.strip("/").split("/"):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def num(x):
    return repr(x) if isinstance(x, float) else str(x)


def load():
    raw = SOURCE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        sys.exit(f"refusing: {SOURCE} SHA-256 {digest} is not the pinned saved result {SOURCE_SHA256}")
    data = json.loads(raw)
    if data["run_id"] != RUN_ID or data["summary"]["n"] != 9:
        sys.exit("refusing: unexpected run_id or n")
    return data


def group_rows(d):
    spec = [
        ("T", "J", "/primary/T_usefulness/J", "/summary/group/T_J", "group: upper bound < 0.20", "upper", J_MAX, "lt"),
        ("T", "C", "/primary/T_usefulness/C", "/summary/group/T_C", "group: lower bound > 0.50", "lower", C_MIN, "gt"),
        ("H", "J", "/primary/H_usefulness/J", "/summary/group/H_J", "group: upper bound < 0.20", "upper", J_MAX, "lt"),
        ("H", "C", "/primary/H_usefulness/C", "/summary/group/H_C", "group: lower bound > 0.50", "lower", C_MIN, "gt"),
        ("T-H", "J", "/primary/delta", "/summary/group/T_minus_H_J", "non-inferiority: upper bound < 0.02", "upper", NI_MARGIN, "lt"),
    ]
    rows = []
    for method, metric, base, summary_ptr, criterion, side, thr, op in spec:
        est = pointer(d, base)
        assert est["df"] == 8 and est["n"] == 9 and est["alpha"] == 0.025
        assert est["two_sided95"] == [est["lower"], est["upper"]]
        bound = est[side]
        met = bound < thr if op == "lt" else bound > thr
        summary_mean = pointer(d, summary_ptr)
        assert abs(summary_mean - est["mean"]) <= 1e-12, (summary_ptr, summary_mean, est["mean"])
        rows.append({
            "method_or_contrast": method,
            "metric": metric,
            "mean": est["mean"],
            "ci95_t_lower": est["lower"],
            "ci95_t_upper": est["upper"],
            "interval": "ordinary two-sided 95% t, df=8",
            "n_participants": est["n"],
            "criterion": criterion,
            "criterion_met": met,
            "mean_summary_field": summary_mean,
            "source_pointer": base,
            "summary_pointer": summary_ptr,
        })
    # Cross-check the derived group flags against the saved failure reasons.
    for m in ("T", "H"):
        reasons = pointer(d, f"/primary/{m}_usefulness/reasons")
        j_row = next(r for r in rows if r["method_or_contrast"] == m and r["metric"] == "J")
        c_row = next(r for r in rows if r["method_or_contrast"] == m and r["metric"] == "C")
        assert (not j_row["criterion_met"]) == ("J_bound_failed" in reasons)
        assert (not c_row["criterion_met"]) == ("C_bound_failed" in reasons)
    ni_row = rows[-1]
    assert ni_row["criterion_met"] == (pointer(d, "/primary/NI") == "ESTABLISHED")
    return rows


def participant_rows(d):
    denominators = {}
    for r in d["instance_metrics"]:
        denominators.setdefault(r["participant"], set()).add(r["denominator"])
    assert len(d["instance_metrics"]) == 54
    rows = []
    for i, p in enumerate(d["summary"]["participants"]):
        den = denominators[p["participant"]]
        assert len(den) == 1, p["participant"]
        rows.append({
            "participant": p["participant"],
            "T_J": p["T_J"],
            "H_J": p["H_J"],
            "T_C": p["T_C"],
            "H_C": p["H_C"],
            "T_minus_H_J": p["T_minus_H_J"],
            "Q_denominator": den.pop(),
            "T_meets_individual_rule": p["T_J"] <= J_MAX and p["T_C"] >= C_MIN,
            "H_meets_individual_rule": p["H_J"] <= J_MAX and p["H_C"] >= C_MIN,
            "source_pointer": f"/summary/participants/{i}",
        })
    assert [r["participant"] for r in rows] == list(range(1, 10))
    for m in ("T", "H"):
        count = sum(r[f"{m}_meets_individual_rule"] for r in rows)
        assert count == pointer(d, f"/primary/{m}_usefulness/participant_guard"), m
        reasons = pointer(d, f"/primary/{m}_usefulness/reasons")
        assert (count < REQUIRED_PEOPLE) == ("7_of_9_failed" in reasons)
    return rows


def decision_rows(d):
    p = d["primary"]
    rows = [
        ("T individual rule (J<=0.20 and C>=0.50): participants meeting", p["T_usefulness"]["participant_guard"], "count", f">= {REQUIRED_PEOPLE} of 9", p["T_usefulness"]["participant_guard"] >= REQUIRED_PEOPLE, "/primary/T_usefulness/participant_guard"),
        ("H individual rule (J<=0.20 and C>=0.50): participants meeting", p["H_usefulness"]["participant_guard"], "count", f">= {REQUIRED_PEOPLE} of 9", p["H_usefulness"]["participant_guard"] >= REQUIRED_PEOPLE, "/primary/H_usefulness/participant_guard"),
        ("T active-fit guard: participants with >=2/3 active non-fallback seeds", p["T_active_people"], "count", f">= {ACTIVE_REQUIRED} of 9", p["T_active_people"] >= ACTIVE_REQUIRED, "/primary/T_active_people"),
        ("H active-fit guard: participants with >=2/3 active non-fallback seeds", p["H_active_people"], "count", f">= {ACTIVE_REQUIRED} of 9", p["H_active_people"] >= ACTIVE_REQUIRED, "/primary/H_active_people"),
        ("Non-inferiority of T to H (margin 0.02)", p["NI"], "saved label", "ESTABLISHED", p["NI"] == "ESTABLISHED", "/primary/NI"),
        ("T usefulness established", p["T_usefulness"]["established"], "saved flag", "true", p["T_usefulness"]["established"] is True, "/primary/T_usefulness/established"),
        ("H qualifies as useful fitted reference (reported, not a fourth success condition)", p["H_useful_fitted_reference"], "saved flag", "true", p["H_useful_fitted_reference"] is True, "/primary/H_useful_fitted_reference"),
        ("Primary composite label", p["t_model_base_label"], "saved label", "", "", "/primary/t_model_base_label"),
        ("Robustness status (bootstrap may only downgrade)", p["robustness_status"], "saved label", "", "", "/primary/robustness_status"),
    ]
    for key, ptr in (("T_J", "/primary/bootstrap/T_J"), ("T_C", "/primary/bootstrap/T_C"),
                     ("H_J", "/primary/bootstrap/H_J"), ("H_C", "/primary/bootstrap/H_C"),
                     ("T_minus_H_J", "/primary/bootstrap/delta")):
        b = pointer(d, ptr)
        assert b["two_sided95"] == [b["lower"], b["upper"]]
        rows.append((f"Saved percentile bootstrap interval, {key} (fixed 10000x9 participant resample indices; robustness only)",
                     f"[{num(b['lower'])}, {num(b['upper'])}]", "interval", "", "", ptr))
    return [dict(zip(("quantity", "value", "kind", "requirement", "requirement_met", "source_pointer"), r)) for r in rows]


def to_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: num(v) if isinstance(v, float) else v for k, v in r.items()})
    return buf.getvalue()


def verify_csv_roundtrip(text, rows):
    """Every float written to CSV must parse back to exactly the saved value."""
    back = list(csv.DictReader(io.StringIO(text)))
    assert len(back) == len(rows)
    for got, want in zip(back, rows):
        for k, v in want.items():
            if isinstance(v, float):
                assert float(got[k]) == v, (k, got[k], v)


def yes(flag):
    return "yes" if flag else "**no**"


def md_group(rows, part_rows, d):
    f = {"J": "{:.4f}", "C": "{:.4f}"}
    out = ["| Quantity | Mean | 95% t interval (df = 8) | Pre-specified criterion | Met |",
           "|---|---:|---:|---|---|"]
    names = {("T", "J"): "T decision loss J", ("T", "C"): "T coverage C",
             ("H", "J"): "H decision loss J", ("H", "C"): "H coverage C",
             ("T-H", "J"): "T − H difference in J"}
    for r in rows:
        if r["method_or_contrast"] == "T-H":
            m, lo, hi = (f"{x:.5f}".replace("-", "−") for x in (r["mean"], r["ci95_t_lower"], r["ci95_t_upper"]))
        else:
            fmt = f[r["metric"]]
            m, lo, hi = (fmt.format(x) for x in (r["mean"], r["ci95_t_lower"], r["ci95_t_upper"]))
        crit = r["criterion"].replace("group: ", "group ").replace("non-inferiority: ", "non-inferiority: ")
        out.append(f"| {names[(r['method_or_contrast'], r['metric'])]} | {m} | [{lo}, {hi}] | {crit} | {yes(r['criterion_met'])} |")
    t5 = sum(x["T_meets_individual_rule"] for x in part_rows)
    h5 = sum(x["H_meets_individual_rule"] for x in part_rows)
    out.append(f"| Participants meeting J ≤ 0.20 and C ≥ 0.50 (T / H) | {t5} / {h5} of 9 | — | at least 7 of 9 | {yes(t5 >= 7)} / {yes(h5 >= 7)} |")
    return "\n".join(out)


def md_participants(rows):
    out = ["| Participant | Evaluation trials (Q) | T: J | H: J | T − H: J | T: C | H: C | T meets J ≤ 0.20 & C ≥ 0.50 | H meets J ≤ 0.20 & C ≥ 0.50 |",
           "|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|"]
    for r in rows:
        diff = f"{r['T_minus_H_J']:.4f}".replace("-", "−")
        out.append(f"| {r['participant']} | {r['Q_denominator']} | {r['T_J']:.4f} | {r['H_J']:.4f} | {diff} | "
                   f"{r['T_C']:.4f} | {r['H_C']:.4f} | {'yes' if r['T_meets_individual_rule'] else 'no'} | "
                   f"{'yes' if r['H_meets_individual_rule'] else 'no'} |")
    return "\n".join(out)


def blocks(d):
    g, p, c = group_rows(d), participant_rows(d), decision_rows(d)
    files = {
        "results/group_estimates.csv": (to_csv(g), g),
        "results/participant_results.csv": (to_csv(p), p),
        "results/decision_criteria.csv": (to_csv(c), c),
    }
    for text, rows in files.values():
        verify_csv_roundtrip(text, rows)
    md = {"group_table": md_group(g, p, d), "participant_table": md_participants(p)}
    return {k: v[0] for k, v in files.items()}, md


def embedded(text, name):
    begin, end = f"<!-- BEGIN GENERATED: {name} -->", f"<!-- END GENERATED: {name} -->"
    if begin not in text or end not in text:
        return None
    return text.split(begin, 1)[1].split(end, 1)[0].strip("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify existing outputs and embedded tables; write nothing")
    args = ap.parse_args()
    d = load()
    files, md = blocks(d)
    problems = []
    if args.check:
        for rel, text in files.items():
            path = ROOT / rel
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                problems.append(f"{rel} differs from a fresh projection")
        docs = {"README.md": ["group_table"], "results/README.md": ["group_table", "participant_table"]}
        for rel, names in docs.items():
            text = (ROOT / rel).read_text(encoding="utf-8")
            for name in names:
                if embedded(text, name) != md[name]:
                    problems.append(f"{rel}: table '{name}' differs from a fresh projection")
        for p in problems:
            print("MISMATCH:", p)
        print("CHECK", "FAILED" if problems else "PASSED", f"({len(files)} CSV files, 3 embedded tables, source {SOURCE_SHA256[:12]}…)")
        return 1 if problems else 0
    for rel, text in files.items():
        (ROOT / rel).write_text(text, encoding="utf-8")
        print("wrote", rel)
    for name, text in md.items():
        print(f"\n<!-- BEGIN GENERATED: {name} -->\n{text}\n<!-- END GENERATED: {name} -->")
    return 0


if __name__ == "__main__":
    sys.exit(main())
