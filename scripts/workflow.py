#!/usr/bin/env python3
"""Resolve local editorial profiles and compile module inputs to validated frontend JSON."""

import argparse
import json
import sys
from pathlib import Path

from validate import (SCHEMAS, check_schema, load_json, load_slot, require, schema_validate, selected_profiles,
                      validate, validate_classification)

COMMON_FIELDS = ("id", "title", "section_ids", "evidence_ids", "decision", "decision_reason", "notes")


def load_module_catalog():
    return load_json(SCHEMAS / "presentation-modules.json")


def component_files():
    return load_json(SCHEMAS / "components.json")["files"]


def load_component(name, files):
    require(name in files, "Unknown module_id: " + name)
    component = load_json(SCHEMAS / files[name])
    require(component["id"] == name, "Component ID differs from index: " + name)
    component["file"] = files[name]
    definitions = component.pop("$defs")
    component.pop("$schema")
    for key in ("input_schema", "frontend_schema"):
        schema = definitions[key]
        check_schema(schema, SCHEMAS / files[name])
        component[key] = schema
    return component


def resolve(selection):
    validate_classification(selection)
    profiles = selected_profiles(selection)
    catalog = load_module_catalog()
    files = component_files()
    selected_modules = {}
    for profile in profiles:
        rules = catalog["article_rules"].get(profile["type"], {})
        if "presentation_hints" in rules:
            profile["presentation_hints"] = rules["presentation_hints"]
        for slot in profile["slots"]:
            conditions = slot.pop("presentation_conditions", {})
            candidates = []
            for name in slot["presentation_modules"]:
                if name not in selected_modules:
                    component = load_component(name, files)
                    selected_modules[name] = {k: v for k, v in component.items()
                                              if k not in ("input_schema", "frontend_schema", "example")}
                module = selected_modules[name]
                candidates.append({"module_id": name, "use_when": conditions.get(name, module["use_when"])})
            slot["presentation_modules"] = candidates
    return {"classification": selection, "profiles": profiles, "modules": selected_modules}


def compile_block(item, contract, sections, evidence):
    name = contract["id"]
    require(contract["availability"] == "supported", name + ": planning only")
    schema_validate(item, contract["input_schema"], SCHEMAS / contract["file"], "$.modules[" + name + "]")
    data = item["data"]
    if name == "text":
        require(len(item["section_ids"]) == 1 and item["section_ids"][0] in sections,
                "Text needs one existing section")
        data = {"body": sections[item["section_ids"][0]]["body"]}
    elif name in ("line_chart", "bar_chart", "timeline"):
        timeline = name == "timeline"
        ids = data["event_ids" if timeline else "measurement_ids"]
        kind = "event" if timeline else "measurement"
        require(all(i in evidence and evidence[i]["kind"] == kind for i in ids),
                name + ": expected " + kind + " evidence")
        if timeline:
            data = {"events": [{"date": evidence[i]["date"], "text": evidence[i]["text"],
                                "evidence_id": i} for i in ids]}
        else:
            data = {key: evidence[ids[0]][key] for key in ("metric", "unit", "region", "statistic")}
            axis = "period" if name == "line_chart" else "category"
            data["points"] = [{"x": evidence[i][axis], "value": evidence[i]["value"],
                               "evidence_id": i} for i in ids]
            if name == "bar_chart":
                data["zero_baseline"] = True
    return {"type": contract["block_type"], **{k: item[k] for k in COMMON_FIELDS}, **data}


def build(selection, rag, analysis, plan):
    require(isinstance(rag, dict) and rag.get("kind") == "rag_input", "Expected RAG input")
    require(isinstance(analysis, dict) and analysis.get("kind") == "analysis", "Expected analysis")
    require(selection is not None, "Expected classification")
    validate(analysis, rag, expected_classification=selection)
    require(isinstance(plan, dict) and set(plan) == {"modules"} and isinstance(plan["modules"], list),
            "Module plan must contain a modules array")
    sections = {s["id"]: s for s in analysis["sections"]}
    evidence = {e["id"]: e for e in analysis["evidence"]}
    files = component_files()
    contracts = {}
    blocks = []
    for item in plan["modules"]:
        require(isinstance(item, dict) and isinstance(item.get("module_id"), str), "Unknown module_id")
        name = item["module_id"]
        if name not in contracts:
            contracts[name] = load_component(name, files)
        blocks.append(compile_block(item, contracts[name], sections, evidence))
    document = {"schema_version": "0.2.0", "kind": "presentation", "analysis": analysis, "blocks": blocks}
    validate(document, require_structure=True)
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("resolve", help="Load the selected profiles and their candidate modules").add_argument(
        "classification", type=Path)
    commands.add_parser("slot", help="Show one slot and its candidate module IDs").add_argument("slot_type")
    commands.add_parser("module", help="Show one module's input and frontend schema").add_argument("module_id")
    compile_cmd = commands.add_parser("build", help="Compile a module plan and emit validated presentation JSON")
    for arg in ("classification", "input", "analysis", "plan"):
        compile_cmd.add_argument("--" + arg, required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "resolve":
            output = resolve(load_json(args.classification))
        elif args.command == "slot":
            output = load_slot(args.slot_type)
        elif args.command == "module":
            output = load_component(args.module_id, component_files())
        else:
            output = build(load_json(args.classification), load_json(args.input),
                           load_json(args.analysis), load_json(args.plan))
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, KeyError, OSError, TypeError, RecursionError) as exc:
        print("INVALID: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
