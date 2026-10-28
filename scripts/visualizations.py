"""Evidence constraints for the nine additional forms in the original selection guide."""

import math


def same(items, keys, require, context):
    for key in keys:
        require(len({x[key] for x in items}) == 1, context + ": incomparable " + key)


def get(evidence, eid, kind, require, context):
    require(eid in evidence and evidence[eid]["kind"] == kind,
            context + ": expected " + kind + " evidence " + eid)
    return evidence[eid]


def numeric(item, require, context, nonnegative=False):
    require(item["value"] is not None, context + ": missing numerical value")
    if nonnegative:
        require(item["value"] >= 0, context + ": negative area/count value")
    return item["value"]


def partition(evidence, pid, require):
    part = get(evidence, pid, "partition", require, pid)
    ids = [part["total_id"]] + part["member_ids"]
    require(len(set(ids)) == len(ids), pid + ": total repeated among partition members")
    items = [get(evidence, eid, "measurement", require, pid) for eid in ids]
    same(items, ("metric", "unit", "region", "statistic", "period"), require, pid)
    values = [numeric(x, require, pid, nonnegative=True) for x in items]
    categories = [x["category"] for x in items[1:]]
    require(all(categories) and len(set(categories)) == len(categories),
            pid + ": partition categories must be distinct and named")
    require(values[0] > 0, pid + ": partition total must be positive")
    require(math.isclose(values[0], sum(values[1:]), rel_tol=1e-9, abs_tol=1e-9),
            pid + ": partition members do not sum to total")
    return part, items


def validate_extended_evidence(evidence, require, date_value):
    for item in evidence.values():
        eid, kind = item["id"], item["kind"]
        if kind in ("entity", "relationship", "text_term"):
            date_value(item["period"])
        if kind == "partition":
            partition(evidence, eid, require)
        elif kind == "relationship":
            for endpoint in ("from_id", "to_id"):
                get(evidence, item[endpoint], "entity", require, eid)
            if item["weight_evidence_id"] is not None:
                weight = get(evidence, item["weight_evidence_id"], "measurement", require, eid)
                numeric(weight, require, eid, nonnegative=True)
                require(weight["period"] == item["period"], eid + ": relationship weight period differs")
        elif kind == "process_link":
            for endpoint in ("from_id", "to_id"):
                get(evidence, item[endpoint], "process_step", require, eid)
        elif kind == "location":
            lat, lon = item["latitude"], item["longitude"]
            require((lat is None) == (lon is None), eid + ": incomplete coordinates")
            require(lat is None or (-90 <= lat <= 90 and -180 <= lon <= 180),
                    eid + ": coordinates out of range")
            require((item["region_code"] is None) == (item["boundary_id"] is None),
                    eid + ": region code requires versioned boundary ID")
            require(lat is not None or item["region_code"] is not None, eid + ": missing geographic locator")
        elif kind == "text_term":
            if item["sample_size"] is not None:
                require(item["sample_size"] > 0 and int(item["sample_size"]) == item["sample_size"],
                        eid + ": invalid text sample size")
            require((item["value"] is None) == (item["unit"] is None), eid + ": text value needs unit")
            if item["value"] is not None:
                numeric(item, require, eid, nonnegative=True)
                require(item["present"] == (item["value"] > 0), eid + ": term presence disagrees with count")


def validate_extended_block(block, evidence, require):
    bid, kind = block["id"], block["type"]
    cited = set(block["evidence_ids"])

    def item(eid, expected):
        require(eid in cited, bid + ": component evidence not cited: " + eid)
        return get(evidence, eid, expected, require, bid)

    def cited_partition(pid):
        part = item(pid, "partition")
        require({part["total_id"], *part["member_ids"]} <= cited,
                bid + ": partition measurements must be cited")
        return partition(evidence, pid, require)

    if kind == "stacked_chart":
        totals = []
        parts = []
        for pid in block["partition_ids"]:
            part, values = cited_partition(pid)
            totals.append(values[0])
            parts.append(part)
        same(totals, ("metric", "unit", "statistic", "period"), require, bid)
        require(len({x["label"] for x in parts}) == len(parts), bid + ": duplicate stacked group label")
        require(len({x["total_id"] for x in parts}) == len(parts), bid + ": duplicate stacked total")
    elif kind == "scatter_plot":
        seen, labels, pairs = set(), set(), []
        for point in block["points"]:
            x = item(point["x_evidence_id"], "measurement")
            y = item(point["y_evidence_id"], "measurement")
            require(x["category"] == y["category"] == point["label"], bid + ": unpaired scatter subject")
            require(x["id"] != y["id"], bid + ": scatter axes repeat one measurement")
            same([x, y], ("period", "region"), require, bid)
            for axis, value in (("x_axis", x), ("y_axis", y)):
                numeric(value, require, bid)
                for key in ("metric", "unit", "statistic"):
                    require(block[axis][key] == value[key], bid + ": scatter axis differs from evidence")
            pair = (x["id"], y["id"])
            require(pair not in seen and point["label"] not in labels, bid + ": duplicate scatter point")
            seen.add(pair)
            labels.add(point["label"])
            pairs.extend([x, y])
        same(pairs, ("period", "region"), require, bid)
    elif kind == "bubble_chart":
        items = [item(eid, "measurement") for eid in block["measurement_ids"]]
        same(items, ("metric", "unit", "region", "statistic", "period"), require, bid)
        require(all(x["category"] for x in items), bid + ": bubbles need category labels")
        require(len({x["category"] for x in items}) == len(items), bid + ": duplicate bubble category")
        for value in items:
            numeric(value, require, bid, nonnegative=True)
        require(any(x["value"] > 0 for x in items), bid + ": all bubbles are zero")
    elif kind == "unit_chart":
        part, values = cited_partition(block["partition_id"])
        require(block["unit_value"] > 0 and int(block["unit_value"]) == block["unit_value"],
                bid + ": unit_value must be a positive integer")
        require(all(int(x["value"]) == x["value"] for x in values), bid + ": unit chart needs integer counts")
        if block["representation"] == "percentage":
            require(values[0]["unit"] == "%" and values[0]["value"] == 100,
                    bid + ": percentage units require a sourced 100-percent partition")
            require(bool(block["notes"]), bid + ": percentage conversion must be explained")
        # The renderer displays an explicit remainder rather than rounding a partial unit.
    elif kind == "map":
        measurements, locations = [], []
        for feature in block["features"]:
            loc = item(feature["location_id"], "location")
            value = item(feature["measurement_id"], "measurement")
            require(value["region"] == loc["label"], bid + ": map value belongs to another location")
            if block["mode"] == "points":
                require(loc["latitude"] is not None, bid + ": point map needs coordinates")
            else:
                require(loc["region_code"] is not None, bid + ": choropleth needs boundary mapping")
            locations.append(loc)
            measurements.append(value)
        same(measurements, ("metric", "unit", "statistic", "period"), require, bid)
        require(len({x["id"] for x in locations}) == len(locations), bid + ": duplicate map location")
        if block["mode"] == "choropleth":
            same(locations, ("boundary_id",), require, bid)
            require(len({x["region_code"] for x in locations}) == len(locations), bid + ": duplicate region code")
    elif kind in ("flowchart", "network_graph"):
        node_kind = "process_step" if kind == "flowchart" else "entity"
        edge_kind = "process_link" if kind == "flowchart" else "relationship"
        nodes = [item(eid, node_kind) for eid in block["node_ids"]]
        edges = [item(eid, edge_kind) for eid in block["edge_ids"]]
        node_ids = set(block["node_ids"])
        for edge in edges:
            require({edge["from_id"], edge["to_id"]} <= node_ids, bid + ": dangling graph edge")
        if kind == "network_graph":
            same(nodes + edges, ("period",), require, bid)
            weights = []
            for edge in edges:
                if edge["weight_evidence_id"] is not None:
                    item(edge["weight_evidence_id"], "measurement")
                    weights.append(edge["weight_evidence_id"])
            require(len(set(weights)) == len(weights), bid + ": shared total duplicated as edge weights")
        else:
            same(edges, ("rule_basis", "version"), require, bid)
            starts = [x["id"] for x in nodes if x["role"] == "start"]
            ends = {x["id"] for x in nodes if x["role"] == "end"}
            require(len(starts) == 1 and bool(ends), bid + ": flow needs one entry and an exit")
            require(bool(evidence[starts[0]]["scope"].strip()), bid + ": flow entry needs audience/scope")
            outgoing = {eid: [] for eid in node_ids}
            incoming = {eid: [] for eid in node_ids}
            for edge in edges:
                outgoing[edge["from_id"]].append(edge)
                incoming[edge["to_id"]].append(edge)
            require(not incoming[starts[0]], bid + ": entry cannot be a return target")
            for node in nodes:
                branches = outgoing[node["id"]]
                require(not branches if node["role"] == "end" else bool(branches),
                        bid + ": missing flow path or nonterminal exit")
                if node["role"] == "decision":
                    require(len(branches) >= 2 and all(e["conditions"] for e in branches),
                            bid + ": decision branches need sourced conditions")
                    require(len({e["label"] for e in branches}) == len(branches), bid + ": duplicate branch label")

            def reachable(seeds, reverse=False):
                reached, pending = set(), list(seeds)
                while pending:
                    current = pending.pop()
                    if current in reached:
                        continue
                    reached.add(current)
                    links = incoming[current] if reverse else outgoing[current]
                    pending.extend(e["from_id" if reverse else "to_id"] for e in links)
                return reached

            require(reachable(starts) == node_ids, bid + ": unreachable flow nodes")
            require(reachable(ends, reverse=True) == node_ids, bid + ": flow has no path to an exit")
    elif kind == "word_cloud":
        terms = [item(eid, "text_term") for eid in block["term_ids"]]
        same(terms, ("corpus", "period", "language", "sample_size", "sampling", "method", "group"), require, bid)
        require(len({x["term"] for x in terms}) == len(terms), bid + ": duplicate cloud term")
        require(all(x["present"] for x in terms), bid + ": cloud contains absent terms")
        if block["mode"] == "presence":
            require(all(x["value"] is None for x in terms), bid + ": presence cloud must use equal text size")
        else:
            same(terms, ("unit",), require, bid)
            for term in terms:
                require(numeric(term, require, bid) > 0, bid + ": weighted cloud needs positive values")
            require(all(x["sample_size"] is not None for x in terms), bid + ": weighted cloud needs sample size")
    elif kind == "treemap":
        nodes = {x["id"]: x for x in block["nodes"]}
        require(len(nodes) == len(block["nodes"]), bid + ": duplicate treemap node")
        require(len({x["measurement_id"] for x in nodes.values()}) == len(nodes), bid + ": duplicate treemap measurement")
        roots = [x for x in nodes.values() if x["parent_id"] is None]
        require(len(roots) == 1, bid + ": treemap needs one root")
        children = {eid: [] for eid in nodes}
        for node in nodes.values():
            item(node["measurement_id"], "measurement")
            if node["parent_id"] is not None:
                require(node["parent_id"] in nodes, bid + ": unknown treemap parent")
                children[node["parent_id"]].append(node["id"])
        partitions = {}
        for pid in block["partition_ids"]:
            part, _ = cited_partition(pid)
            require(part["total_id"] not in partitions, bid + ": duplicate treemap partition")
            partitions[part["total_id"]] = part
        used, seen = set(), set()

        def walk(nid):
            require(nid not in seen, bid + ": treemap cycle")
            seen.add(nid)
            if children[nid]:
                mid = nodes[nid]["measurement_id"]
                require(mid in partitions, bid + ": missing parent partition")
                require(set(partitions[mid]["member_ids"]) == {nodes[c]["measurement_id"] for c in children[nid]},
                        bid + ": treemap children disagree with partition")
                used.add(mid)
                for child in children[nid]:
                    walk(child)

        walk(roots[0]["id"])
        require(seen == set(nodes), bid + ": disconnected treemap nodes")
        require(used == set(partitions), bid + ": unused treemap partition")
