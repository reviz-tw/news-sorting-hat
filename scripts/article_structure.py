"""Validate editorial role mappings independently of visual block selection."""


def validate_structure(analysis, catalog, require):
    structure = analysis.get("article_structure")
    if structure is None:
        return  # Legacy 0.2.0 documents; callers can require the extension.
    cls = analysis["classification"]
    selected = ([cls["primary"]] + cls["secondary"]) if cls["primary"] else ["unclassified"]
    require(structure["templates"] == selected, "Structure templates disagree with classification")
    templates = {t["type"]: t for t in catalog["templates"] + [catalog["fallback"]]}
    expected = {(typ, slot["id"]): slot for typ in selected for slot in templates[typ]["slots"]}
    sections = {s["id"]: s for s in analysis["sections"]}
    evidence = {e["id"] for e in analysis["evidence"]}
    seen_roles, seen_nodes, covered_sections, active_types = set(), set(), set(), set()
    for node in structure["nodes"]:
        require(node["id"] not in seen_nodes, "Duplicate structure node ID")
        seen_nodes.add(node["id"])
        require(set(node["section_ids"]) <= set(sections), "Structure references unknown section")
        require(set(node["evidence_ids"]) <= evidence, "Structure references unknown evidence")
        allowed = {eid for sid in node["section_ids"] for eid in sections[sid]["evidence_ids"]}
        require(set(node["evidence_ids"]) <= allowed, "Structure evidence outside mapped sections")
        status = node["status"]
        if status in ("covered", "partial"):
            require(bool(node["section_ids"]) and bool(node["evidence_ids"]),
                    "Covered/partial structure nodes need sections and evidence")
        if status == "missing":
            require(not node["evidence_ids"], "Missing structure node must not claim supporting evidence")
        if status == "not_applicable":
            require(not node["section_ids"] and not node["evidence_ids"],
                    "Not-applicable structure node must have empty mappings")
        else:
            covered_sections.update(node["section_ids"])
        for role in node["roles"]:
            key = (role["type"], role["slot"])
            require(key in expected, "Unknown or unselected article role")
            require(key not in seen_roles, "Article role assigned more than once")
            seen_roles.add(key)
            if status != "not_applicable":
                active_types.add(role["type"])
            if role["type"] == selected[0] and expected[key]["priority"] == "core":
                require(status != "not_applicable", "Primary core role must be addressed or marked missing")
    require(seen_roles == set(expected), "Structure must account for every selected template slot")
    require(covered_sections == set(sections), "Structure must map every answer section")
    require(active_types == set(selected), "Each classified type needs an active article role")
