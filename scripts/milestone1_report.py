"""Draft tables of docs/milestone1-results.md from eval/results/ms1-old.json and ms1-new.json
(read-only; the answer text comes from request_logs, where emails and phones are redacted).

    uv run python scripts/milestone1_report.py > /tmp/ms1-tables.md
"""

import json
import statistics as st
from collections import Counter, defaultdict

from cta.eval.metrics import scorable_gold
from cta.eval.questions import load_questions
from cta.eval.run_answers import aggregate
from cta.graph import contact
from cta.index.db import connect
from cta.settings import ROOT, load_models

R = ROOT / "eval" / "results"
CHAIN_TEST = ["q78", "q80", "q82", "q84", "q86"]


def load(label):
    return json.loads((R / f"{label}.json").read_text(encoding="utf-8"))


def texts(label):
    with connect() as c:
        run_id = c.execute("SELECT id FROM eval_runs WHERE label=%s", (label,)).fetchone()[0]
        rows = c.execute(
            "SELECT question, answer FROM request_logs WHERE run_id=%s", (run_id,)
        ).fetchall()
    return dict(rows)


def cnt(records, field, gold_kinds=("normal",)):
    c = Counter(r[field] for r in records if r["gold_kind"] in gold_kinds and r[field])
    return c


def fmt(c, keys):
    n = sum(c.values())
    return f"{n}: " + " / ".join(f"{c.get(k, 0)} {k}" for k in keys)


def med(xs):
    return f"{st.median(xs):.0f}" if xs else "-"


def p95(xs):
    return f"{sorted(xs)[max(0, round(0.95 * len(xs)) - 1)]:.0f}" if xs else "-"


def headline(old, new):
    out = ["| metric | OLD | NEW |", "|---|---|---|"]
    ro, rn = old["retrieval"], new["retrieval"]
    for k in ("recall@5", "precision@5", "hit@5", "mrr"):
        out.append(f"| retrieval {k} (n={ro['n']} scored) | {ro[k]:.3f} | {rn[k]:.3f} |")
    for name, f in (
        ("correctness, normal gold", "correctness"),
        ("faithfulness, normal gold", "faithfulness"),
    ):
        keys = (
            ("correct", "partial", "incorrect") if f == "correctness" else ("yes", "partly", "no")
        )
        out.append(
            f"| {name} (n: counts) | {fmt(cnt(old['per_question'], f), keys)} | {fmt(cnt(new['per_question'], f), keys)} |"
        )
    for label, r in (("OLD", old), ("NEW", new)):
        pass

    def ab(r):
        pq = r["per_question"]
        ag = [q for q in pq if q["gold_kind"] == "abstain"]
        ans = [q for q in pq if q["gold_kind"] in ("normal", "no_advice")]
        return (
            f"{sum(q['correctness'] == 'correct' for q in ag)} of {len(ag)} ABSTAIN-gold abstained; "
            f"wrongly abstained {sum(q['abstained'] for q in ans)} of {len(ans)} answerable"
        )

    out.append(f"| abstention | {ab(old)} | {ab(new)} |")

    def na(r):
        x = [q for q in r["per_question"] if q["gold_kind"] == "no_advice"]
        return ", ".join(f"{q['id']} {q['correctness']}" for q in x) or "-"

    out.append(f"| NO ADVICE gold | {na(old)} | {na(new)} |")

    def cal(r):
        x = [q for q in r["per_question"] if q["gold_kind"] == "calendar_only"]
        c = Counter((q["calendar_v2"] or {}).get("correctness") or q["correctness"] for q in x)
        return f"{len(x)}: " + " / ".join(
            f"{c.get(k, 0)} {k}" for k in ("correct", "partial", "incorrect")
        )

    out.append(f"| calendar-only, scoring v2 (n: counts) | {cal(old)} | {cal(new)} |")
    out.append(
        f"| failure labels | {dict(old['failure_labels'])} | {dict(new['failure_labels'])} |"
    )
    for label, r in (("cost per request (USD, answer+rerank+route+judge)", None),):
        pass

    def cost(r):
        a = r["answers"]["cost"]
        total = a["judge_usd"] + a["answer_usd"]
        return (
            f"{a['per_request_usd']:.5f}; run total ${total:.4f} "
            f"(judge {a['judge_usd']:.4f}; answer incl. router calls and rerank {a['answer_usd']:.4f})"
        )

    out.append(f"| cost per request | {cost(old)} | {cost(new)} |")
    for label, key in (("latency total median / p95 ms", "total"),):
        lo, ln = old["answers"]["latency_ms"], new["answers"]["latency_ms"]
        out.append(
            f"| {label} | {lo['total_median']} / {lo['total_p95']} | {ln['total_median']} / {ln['total_p95']} |"
        )
    return "\n".join(out)


def by_type(old, new):
    out = [
        "| type | n | OLD correct / partial / incorrect (normal gold) | NEW | OLD abstained / NEW abstained |",
        "|---|---|---|---|---|",
    ]
    types = ["lookup", "multi_chunk", "time_sensitive", "ambiguous", "unanswerable"]
    for t in types:
        po = [q for q in old["per_question"] if q["type"] == t]
        pn = [q for q in new["per_question"] if q["type"] == t]
        keys = ("correct", "partial", "incorrect")
        out.append(
            f"| {t} | {len(po)} | {fmt(cnt(po, 'correctness'), keys)} | {fmt(cnt(pn, 'correctness'), keys)} | {sum(q['abstained'] for q in po)} / {sum(q['abstained'] for q in pn)} |"
        )
    return "\n".join(out)


def by_route(new):
    g = defaultdict(list)
    for q in new["per_question"]:
        g[q["route"]].append(q)
    out = [
        "| route (NEW) | n | latency median / p95 ms | answer + router + rerank cost per request | judge cost per request |",
        "|---|---|---|---|---|",
    ]
    for route, qs in sorted(g.items()):
        lat = [q["latency_ms"] for q in qs]
        ac = st.mean((q.get("answer_cost") or 0) + (q.get("rerank_cost") or 0) for q in qs)
        jc = st.mean(q.get("judge_cost") or 0 for q in qs)
        out.append(f"| {route} | {len(qs)} | {med(lat)} / {p95(lat)} | {ac:.5f} | {jc:.5f} |")
    lat = [q["latency_ms"] for q in old["per_question"]] if False else []
    return "\n".join(out)


def chain_table(old, new, qs):
    out = [
        "| id | OLD correctness / faithfulness | NEW route, correctness / faithfulness | gold catalog sources in what the answerer received (OLD, NEW) |",
        "|---|---|---|---|",
    ]
    o = {q["id"]: q for q in old["per_question"]}
    n = {q["id"]: q for q in new["per_question"]}
    for i in CHAIN_TEST:
        gold = [g["id"] for g in qs[i]["gold_sources"]]

        def got(q):
            if q["route"] in ("chain",):
                ids = set(q["router"]["chain"]["source_ids"])
            else:
                ids = {x["id"] for x in q["retrieved"][:5]}
            return f"{len(set(gold) & ids)}/{len(gold)}" if gold else "no gold"

        out.append(
            f"| {i} ({qs[i]['type']}) | {o[i]['correctness']} / {o[i]['faithfulness']} | {n[i]['route']}, {n[i]['correctness']} / {n[i]['faithfulness']} | {got(o[i])}, {got(n[i])} |"
        )
    return "\n".join(out)


def contact_table(new, tx):
    qs = {q["id"]: q for q in load_questions()}
    cfg = contact.load_contacts()
    out = ["| id | question | path | office added | line added |", "|---|---|---|---|---|"]
    for q in new["per_question"]:
        if not q["abstained"]:
            continue
        key = q["router"].get("contact_office")
        path = (
            q["abstain_reason"]
            if q["abstain_reason"] and len(q["abstain_reason"]) < 30
            else "model-written"
        )
        out.append(
            f"| {q['id']} | {qs[q['id']]['question']} | {q['route']} / {path} | {key} | {contact.contact_line(key, cfg) if key else '-'} |"
        )
    return "\n".join(out)


def failures(label, r, tx, qs):
    out = []
    by = defaultdict(list)
    for q in r["per_question"]:
        bad = (
            q["label"]
            or q["correctness"] in ("partial", "incorrect")
            or q["faithfulness"] in ("partly", "no")
        )
        if bad:
            by[q["type"]].append(q)
    for t, items in sorted(by.items()):
        out.append(f"**{t}**\n")
        for q in items:
            text = next(
                v
                for k, v in tx.items()
                if k
                == __import__("cta.redact", fromlist=["redact"]).redact(qs[q["id"]]["question"])
            )
            first = text.strip().splitlines()[0][:220]
            out.append(
                f"- {q['id']} [{label}] label: {q['label'] or '-'}; correctness {q['correctness']}; faithfulness {q['faithfulness']}; route {q['route']}; abstained {q['abstained']}. Q: {qs[q['id']]['question']} A: {first}"
            )
        out.append("")
    return "\n".join(out)


def baseline_consistency(old):
    base = load("baseline-final")
    ids = [q["id"] for q in base["per_question"]]
    b = {q["id"]: q for q in base["per_question"]}
    o = {q["id"]: q for q in old["per_question"]}
    out = [
        "| id | baseline-final (rubric v2) correctness / faithfulness / abstained | ms1-old (rubric v3) | same? |",
        "|---|---|---|---|",
    ]
    same = 0
    for i in ids:
        x, y = b[i], o[i]
        s = (x["correctness"], x["faithfulness"], x["abstained"]) == (
            y["correctness"],
            y["faithfulness"],
            y["abstained"],
        )
        same += s
        out.append(
            f"| {i} | {x['correctness']} / {x['faithfulness']} / {x['abstained']} | {y['correctness']} / {y['faithfulness']} / {y['abstained']} | {'yes' if s else 'NO'} |"
        )
    out.append(f"\nSame verdicts and abstention on {same} of {len(ids)}.")
    return "\n".join(out)


def main():
    old, new = load("ms1-old"), load("ms1-new")
    qs = {q["id"]: q for q in load_questions()}
    to, tn = texts("ms1-old"), texts("ms1-new")
    print("## Headline\n\n" + headline(old, new))
    print("\n## By type\n\n" + by_type(old, new))
    print("\n## NEW by route\n\n" + by_route(new))
    print("\n## Chain questions\n\n" + chain_table(old, new, qs))
    print("\n## Contact check (NEW abstentions)\n\n" + contact_table(new, tn))
    print("\n## OLD against the stored baseline-final\n\n" + baseline_consistency(old))
    print("\n## NEW failures\n\n" + failures("NEW", new, tn, qs))
    print("\n## OLD failures\n\n" + failures("OLD", old, to, qs))
    cfg = load_models()
    print(
        "\n## Resolved NEW config\n\n```\n"
        + json.dumps(
            {
                k: cfg[k]
                for k in (
                    "chat_model",
                    "judge_model",
                    "answer",
                    "retrieval",
                    "rerank",
                    "router",
                    "eval",
                )
            },
            indent=1,
        )
        + "\n```"
    )


if __name__ == "__main__":
    main()
