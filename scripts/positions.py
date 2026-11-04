"""Check longitudinal claim identity, provenance and date comparability."""

import calendar
import datetime as dt


def validate_positions(evidence, require, date_value):
    identities, issues = {}, {}
    for claim in evidence.values():
        if claim["kind"] != "claim" or "position" not in claim:
            continue
        pos = claim["position"]
        for index, key, label in ((identities, "stakeholder_id", "stakeholder_name"),
                                  (issues, "issue_id", "issue")):
            require(pos[key] not in index or index[pos[key]] == pos[label],
                    "Position identity/issue label differs for the same ID")
            index[pos[key]] = pos[label]
        if pos["statement_date"] is not None:
            date_value(pos["statement_date"])

    def interval(value):
        start = date_value(value)
        if len(value) == 4:
            return start, dt.date(start.year, 12, 31)
        if len(value) == 7:
            return start, dt.date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
        return start, start

    for comparison in evidence.values():
        if comparison["kind"] != "stance_comparison":
            continue
        claims = []
        for cid in comparison["claim_ids"]:
            require(cid in evidence and evidence[cid]["kind"] == "claim"
                    and "position" in evidence[cid], "Stance comparison needs positioned claims")
            claim = evidence[cid]
            pos = claim["position"]
            require(pos["stakeholder_id"] == comparison["stakeholder_id"]
                    and pos["issue_id"] == comparison["issue_id"],
                    "Stance comparison mixes stakeholders or issues")
            claims.append(claim)
        cited = {(r["source_id"], r["chunk_id"]) for r in comparison["refs"]}
        needed = {(r["source_id"], r["chunk_id"]) for c in claims for r in c["refs"]}
        require(needed <= cited, "Stance comparison must retain claim sources")
        if comparison["assessment"] in ("changed", "consistent", "conditional"):
            dates = [c["position"]["statement_date"] for c in claims]
            require(all(dates), "Temporal assessment requires known statement dates")
            ranges = [interval(d) for d in dates]
            require(all(a[1] < b[0] for a, b in zip(ranges, ranges[1:])),
                    "Temporal claims must be chronological with non-overlapping date precision")
