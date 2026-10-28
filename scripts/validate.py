#!/usr/bin/env python3
"""Validate News Sorting Hat contracts using the stdlib; not a general schema engine."""

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from visualizations import validate_extended_block, validate_extended_evidence

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
KEYWORDS = {"$schema", "$defs", "$ref", "type", "const", "enum", "properties",
            "required", "additionalProperties", "items", "minItems", "uniqueItems",
            "minLength", "pattern", "oneOf"}


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def load_json(path):
    def reject_constant(value):
        raise ValidationError("Non-finite JSON number: " + value)

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result

    return json.loads(Path(path).read_text(encoding="utf-8"),
                      parse_constant=reject_constant, object_pairs_hook=unique_keys)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def check_schema(schema):
    """Fail closed when a schema introduces unsupported keywords, even in unused branches."""
    require(not (set(schema) - KEYWORDS),
            "Unsupported schema keywords: " + str(set(schema) - KEYWORDS))
    for key in ("$defs", "properties"):
        for child in schema.get(key, {}).values():
            check_schema(child)
    if "items" in schema:
        check_schema(schema["items"])
    for child in schema.get("oneOf", []):
        check_schema(child)


def schema_validate(value, schema, filename, path="$"):
    if "$ref" in schema:
        filepart, _, pointer = schema["$ref"].partition("#")
        target = (filename.parent / filepart).resolve() if filepart else filename
        require(target.parent == SCHEMAS.resolve(), "Schema references must stay in schemas/")
        resolved = load_json(target)
        if pointer:
            require(pointer.startswith("/"), "Only JSON pointer references are supported")
            for token in pointer[1:].split("/"):
                resolved = resolved[token.replace("~1", "/").replace("~0", "~")]
        schema_validate(value, resolved, target, path)
        return
    if "oneOf" in schema:
        variants = schema["oneOf"]
        # Use the discriminant for useful error messages, while still checking uniqueness.
        matches = []
        for variant in variants:
            try:
                schema_validate(value, variant, filename, path)
                matches.append(variant)
            except ValidationError:
                pass
        if len(matches) != 1:
            if isinstance(value, dict):
                for variant in variants:
                    props = variant.get("properties", {})
                    for key in ("type", "kind"):
                        if key in props and props[key].get("const") == value.get(key):
                            schema_validate(value, variant, filename, path)
            raise ValidationError(path + ": expected exactly one allowed variant")
        return
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    valid_types = {"object": isinstance(value, dict), "array": isinstance(value, list),
                   "string": isinstance(value, str), "null": value is None,
                   "boolean": isinstance(value, bool),
                   "number": type(value) in (int, float) and math.isfinite(value)}
    require(not types or any(valid_types[t] for t in types), path + ": wrong type")
    if "const" in schema:
        require(canonical(value) == canonical(schema["const"]), path + ": wrong constant")
    if "enum" in schema:
        require(canonical(value) in [canonical(x) for x in schema["enum"]],
                path + ": not in allowed values")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), path + ": missing required fields")
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(props), path + ": unexpected fields " + str(set(value) - set(props)))
        for key in value.keys() & props.keys():
            schema_validate(value[key], props[key], filename, path + "." + key)
    if isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0), path + ": too few items")
        if schema.get("uniqueItems"):
            require(len({canonical(x) for x in value}) == len(value), path + ": duplicate items")
        for i, child in enumerate(value):
            if "items" in schema:
                schema_validate(child, schema["items"], filename, f"{path}[{i}]")
    if isinstance(value, str):
        require(len(value.strip()) >= schema.get("minLength", 0), path + ": empty text")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, path + ": invalid pattern")


def date_value(value):
    require(re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", value) is not None,
            "Invalid date: " + value)
    parts = [int(x) for x in value.split("-")]
    try:
        return dt.date(*(parts + [1] * (3 - len(parts))))
    except ValueError as exc:
        raise ValidationError("Invalid calendar date: " + value) from exc


def timestamp(value):
    try:
        require("T" in value, "Timestamp must include date and time")
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "Timestamp needs timezone: " + value)
    except ValueError as exc:
        raise ValidationError("Invalid timestamp: " + value) from exc


def index_unique(items, label):
    result = {item["id"]: item for item in items}
    require(len(result) == len(items), "Duplicate " + label + " ID")
    return result


def validate_sources(document):
    timestamp(document["as_of"])
    sources = index_unique(document["sources"], "source")
    chunks = {}
    for source_id, source in sources.items():
        if source["url"] is not None:
            url = urlsplit(source["url"])
            require(url.scheme in ("http", "https") and bool(url.netloc), "Unsafe or invalid source URL")
        for key in ("published_at", "updated_at"):
            if source[key] is not None:
                timestamp(source[key])
        chunks[source_id] = index_unique(source["chunks"], "chunk")
    return chunks


def validate_analysis(analysis, rag_input=None):
    chunks = validate_sources(analysis)
    if rag_input is not None:
        for key in ("question", "as_of", "sources"):
            require(analysis[key] == rag_input[key], "Analysis changed input " + key)
    evidence = index_unique(analysis["evidence"], "evidence")
    sections = index_unique(analysis["sections"], "section")

    def refs_exist(ids, context):
        require(set(ids) <= set(evidence), context + ": unknown evidence ID")

    for item in evidence.values():
        require(len({(r["source_id"], r["chunk_id"]) for r in item["refs"]}) == len(item["refs"]),
                item["id"] + ": duplicate source references")
        for ref in item["refs"]:
            require(ref["source_id"] in chunks and ref["chunk_id"] in chunks[ref["source_id"]],
                    item["id"] + ": unknown source/chunk")
        if item["kind"] == "inference":
            refs_exist(item["based_on"], item["id"])
        if item["kind"] in ("event", "measurement"):
            date_value(item["date"] if item["kind"] == "event" else item["period"])
        if item["kind"] == "claim" and item["verbatim"]:
            require(any(item["text"] in chunks[r["source_id"]][r["chunk_id"]]["text"]
                        for r in item["refs"]), item["id"] + ": verbatim quote missing from source")
    visited, active = set(), set()

    def visit(eid):
        require(eid not in active, "Inference dependency cycle")
        if eid in visited:
            return
        active.add(eid)
        for parent in evidence[eid].get("based_on", []):
            visit(parent)
        active.remove(eid)
        visited.add(eid)

    for eid in evidence:
        visit(eid)
    validate_extended_evidence(evidence, require, date_value)
    cls = analysis["classification"]
    require((cls["status"] == "undetermined") == (cls["primary"] is None),
            "Classification status and primary disagree")
    require(cls["primary"] not in cls["secondary"], "Primary repeated in secondary")
    require(cls["status"] != "undetermined" or not cls["secondary"], "Undetermined must have no secondary")
    require(cls["status"] == "undetermined" or bool(cls["evidence_ids"]), "Classification needs evidence")
    refs_exist(cls["evidence_ids"], "classification")
    for section in sections.values():
        refs_exist(section["evidence_ids"], section["id"])
        require(bool(section["evidence_ids"]) or analysis["status"] == "insufficient",
                section["id"] + ": section needs evidence")
    for limitation in analysis["limitations"]:
        refs_exist(limitation["evidence_ids"], "limitation")
    require(analysis["status"] == "complete" or bool(analysis["limitations"]),
            "Partial/insufficient answer must explain limitations")
    return evidence, sections


def consecutive(previous, current):
    if len(previous) == 4:
        return int(current) == int(previous) + 1
    a, b = date_value(previous), date_value(current)
    if len(previous) == 7:
        return b.year * 12 + b.month == a.year * 12 + a.month + 1
    return b == a + dt.timedelta(days=1)


def validate_blocks(document, evidence, sections):
    blocks = index_unique(document["blocks"], "block")
    covered = set()
    for block in blocks.values():
        bid, kind = block["id"], block["type"]
        require(set(block["section_ids"]) <= set(sections), bid + ": unknown section")
        allowed = {eid for sid in block["section_ids"] for eid in sections[sid]["evidence_ids"]}
        cited = set(block["evidence_ids"])
        require(cited <= allowed, bid + ": evidence outside selected sections")
        visual = kind not in ("text", "quote")
        require((block["decision"] == "visual_selected") == visual, bid + ": invalid decision for component")
        if kind == "text":
            require(len(block["section_ids"]) == 1, bid + ": text must preserve one section")
            sid = block["section_ids"][0]
            require(block["body"] == sections[sid]["body"] and cited == set(sections[sid]["evidence_ids"]),
                    bid + ": text must preserve section body and evidence")
            covered.add(sid)
        elif kind == "table":
            for row in block["rows"]:
                require(len(row) == len(block["columns"]), bid + ": table width mismatch")
                for cell in row:
                    require(set(cell["evidence_ids"]) <= cited, bid + ": cell evidence missing from block")
        elif kind in ("line_chart", "bar_chart"):
            points = block["points"]
            require(len({p["x"] for p in points}) == len(points), bid + ": duplicate chart x")
            require(len({p["evidence_id"] for p in points}) == len(points), bid + ": duplicate chart evidence")
            count = 0
            periods = []
            for point in points:
                require(point["evidence_id"] in cited, bid + ": chart point not cited")
                item = evidence[point["evidence_id"]]
                require(item["kind"] == "measurement", bid + ": chart needs measurement evidence")
                require(point["value"] == item["value"], bid + ": chart value differs from evidence")
                for key in ("metric", "unit", "region", "statistic"):
                    require(block[key] == item[key], bid + ": incomparable " + key)
                require(point["x"] == item["period" if kind == "line_chart" else "category"],
                        bid + ": chart x differs from evidence")
                periods.append(item["period"])
                count += point["value"] is not None
            require(count >= (3 if kind == "line_chart" else 2), bid + ": not enough non-null points")
            if kind == "line_chart":
                require(len({len(p) for p in periods}) == 1, bid + ": mixed date precision")
                require(all(consecutive(a, b) for a, b in zip(periods, periods[1:])),
                        bid + ": unsorted or missing periods; use table/text or sourced null points")
                require(len({evidence[p["evidence_id"]]["category"] for p in points}) == 1,
                        bid + ": mixed categories")
            else:
                require(len(set(periods)) == 1, bid + ": bar chart periods differ")
            require(all(p["value"] is not None for p in points) or bool(block["notes"]),
                    bid + ": missing data must be explained in notes")
        elif kind == "timeline":
            dates = []
            seen = set()
            for event in block["events"]:
                require(event["evidence_id"] in cited, bid + ": timeline event not cited")
                require(event["evidence_id"] not in seen, bid + ": duplicate timeline event")
                seen.add(event["evidence_id"])
                item = evidence[event["evidence_id"]]
                require(item["kind"] == "event" and event["date"] == item["date"]
                        and event["text"] == item["text"], bid + ": timeline differs from event evidence")
                dates.append(event["date"])
            require(dates == sorted(dates), bid + ": timeline is not chronological")
        elif kind == "quote":
            require(block["evidence_id"] in cited, bid + ": quote not cited")
            item = evidence[block["evidence_id"]]
            require(item["kind"] == "claim" and item["verbatim"], bid + ": quote needs verbatim claim")
        else:
            validate_extended_block(block, evidence, require)
    require(covered == set(sections), "Every section needs its complete text block")


def validate(document, rag_input=None, expected_analysis=None):
    # Validate schemas up front, including unvisited variants.
    for schema_file in SCHEMAS.glob("*.schema.json"):
        check_schema(load_json(schema_file))
    require(isinstance(document, dict), "Document must be an object")
    kind = document.get("kind")
    names = {"rag_input": "rag-input", "analysis": "analysis", "presentation": "presentation"}
    require(kind in names, "Unknown document kind")
    filename = SCHEMAS / (names[kind] + ".schema.json")
    schema_validate(document, load_json(filename), filename)
    if kind == "rag_input":
        require(rag_input is None and expected_analysis is None, "Input validation takes no comparison flags")
        validate_sources(document)
        return
    if rag_input is not None:
        require(rag_input.get("kind") == "rag_input", "--input must be rag_input")
        validate(rag_input)
    analysis = document["analysis"] if kind == "presentation" else document
    evidence, sections = validate_analysis(analysis, rag_input)
    if expected_analysis is not None:
        require(kind == "presentation", "--analysis applies only to presentation")
        require(expected_analysis.get("kind") == "analysis", "--analysis must be analysis")
        validate(expected_analysis, rag_input)
        require(analysis == expected_analysis, "Presentation changed first-stage analysis")
    if kind == "presentation":
        validate_blocks(document, evidence, sections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--input", type=Path, help="Original RAG input to compare")
    parser.add_argument("--analysis", type=Path, help="Original first-stage output to compare")
    args = parser.parse_args()
    try:
        validate(load_json(args.document), load_json(args.input) if args.input else None,
                 load_json(args.analysis) if args.analysis else None)
    except (ValidationError, OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print("INVALID: " + str(exc), file=sys.stderr)
        return 1
    print("VALID: " + str(args.document))
    return 0


if __name__ == "__main__":
    sys.exit(main())
