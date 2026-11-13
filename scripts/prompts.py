"""Render self-contained model prompts; models never need repository file access."""

import copy
import json
import re
from pathlib import Path

if __package__:
    from .validate import SCHEMAS, load_json, require, resolve_schema_ref, validate
    from .workflow import resolve
else:
    from validate import SCHEMAS, load_json, require, resolve_schema_ref, validate
    from workflow import resolve

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "classification": ROOT / "skills/news-classification/SKILL.md",
    "analysis": ROOT / "skills/news-analysis/SKILL.md",
    "presentation": ROOT / "skills/news-presentation/SKILL.md",
    "slot": ROOT / "skills/news-analysis/slot.md",
}
INPUT_MARKER = "<!-- INPUT -->"
PLACEHOLDER = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z_0-9]*(?:\.[a-zA-Z_][a-zA-Z_0-9]*)*)\s*}}")


def render_template(template, values):
    """Substitute dotted dict keys once; do not evaluate expressions or inserted text."""
    skeleton = PLACEHOLDER.sub("", template)
    if "{{" in skeleton or "}}" in skeleton:
        raise ValueError("Unsupported prompt placeholder syntax")

    def substitute(match):
        value = values
        for key in match.group(1).split("."):
            if not isinstance(value, dict) or key not in value:
                raise ValueError("Missing prompt variable: " + match.group(1))
            value = value[key]
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

    return PLACEHOLDER.sub(substitute, template)


def inline_schema(schema, filename):
    """Expand local schema references before supplying them to the model."""
    if isinstance(schema, bool):
        return schema
    if "$ref" in schema:
        resolved, origin = resolve_schema_ref(schema, filename)
        return inline_schema(resolved, origin)
    expanded = copy.deepcopy(schema)
    for key in ("properties", "$defs"):
        if key in expanded:
            expanded[key] = {name: inline_schema(value, filename)
                             for name, value in expanded[key].items()}
    if "items" in expanded:
        expanded["items"] = inline_schema(expanded["items"], filename)
    if "oneOf" in expanded:
        expanded["oneOf"] = [inline_schema(value, filename) for value in expanded["oneOf"]]
    return expanded


def model_data(data):
    """Drop repository navigation metadata, keeping source URLs and editorial rules."""
    data = copy.deepcopy(data)
    for category in data.get("categories", []):
        category.pop("file", None)
    for group in ("modules", "components"):
        for component in data.get(group, {}).values():
            origin = SCHEMAS / component.get("file", "analysis.schema.json")
            for key in ("input_schema", "frontend_schema"):
                if key in component:
                    component[key] = inline_schema(component[key], origin)
            component.pop("reference", None)
            component.pop("file", None)
    return data


def build_prompt_request(stage, data, response_schema, *, rewritten_question=None,
                         attempt=1, repair=None):
    """Return a ready-to-send prompt plus the structured adapter fields."""
    if stage not in TEMPLATES:
        raise ValueError("Unknown prompt stage: " + str(stage))
    if type(attempt) is not int or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    template = TEMPLATES[stage].read_text(encoding="utf-8")
    if template.count(INPUT_MARKER) != 1:
        raise ValueError("Template must contain exactly one INPUT marker")
    instruction, context_template = template.split(INPUT_MARKER)
    if "{{" in instruction or "}}" in instruction:
        raise ValueError("Prompt variables must follow the INPUT marker")
    prepared = model_data(data)
    question = rewritten_question
    if question is None:
        question = prepared.get("rag_input", prepared.get("analysis", {})).get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("rewritten_question must be a nonempty string")
    # Callers supply a fully expanded schema. Reject accidental unresolved references.
    def check_refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                raise ValueError("Expand response_schema references before rendering")
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)
    check_refs(response_schema)
    values = {**prepared, "rewritten_question": question,
              "response_schema": response_schema, "attempt": attempt, "repair": repair}
    request = {
        "stage": stage, "instruction": instruction.strip(), "data": prepared,
        "response_schema": copy.deepcopy(response_schema), "attempt": attempt,
        "rewritten_question": question,
        "prompt": instruction.strip() + "\n\n" + render_template(context_template.strip(), values),
    }
    if repair is not None:
        request["repair"] = copy.deepcopy(repair)
    return request


def build_slot_request(rag_input, selection, slot_type, *, rewritten_question=None,
                       attempt=1, repair=None):
    """Prepare one slot draft request; orchestration/merging remains the caller's job."""
    require(isinstance(rag_input, dict) and rag_input.get("kind") == "rag_input", "Expected RAG input")
    validate(rag_input)
    context = resolve(selection)
    matches = [(profile, slot) for profile in context["profiles"] for slot in profile["slots"]
               if slot["type"] == slot_type]
    require(len(matches) == 1, "Slot is not part of the selected article types")
    profile, slot = matches[0]
    article_type = {key: value for key, value in profile.items() if key != "slots"}
    data = {
        "rag_input": rag_input, "article_type": article_type, "slot": slot,
        "is_primary": profile is context["profiles"][0],
        "modules": {item["module_id"]: context["modules"][item["module_id"]]
                    for item in slot["presentation_modules"]},
    }
    filename = SCHEMAS / "slot-draft.schema.json"
    schema = inline_schema(load_json(filename), filename)
    schema["properties"]["slot_type"] = {"const": slot_type}
    return build_prompt_request("slot", data, schema, rewritten_question=rewritten_question,
                                attempt=attempt, repair=repair)
