import os
import json
import csv
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
import re


def parse_pnml(pnml_path):
    tree = ET.parse(pnml_path)
    root = tree.getroot()

    all_transitions = {}
    visible_transitions = {}
    places = set()
    arcs = []

    for t in root.findall(".//transition"):
        tid = t.get("id")
        name_elem = t.find("./name/text")
        tname = name_elem.text if name_elem is not None else tid

        toolspecific = t.find("./toolspecific")
        is_invisible = (
            toolspecific is not None
            and toolspecific.get("activity") == "$invisible$"
        )

        all_transitions[tid] = tname
        if not is_invisible:
            visible_transitions[tid] = tname

    for p in root.findall(".//place"):
        pid = p.get("id")
        if pid:
            places.add(pid)

    for arc in root.findall(".//arc"):
        src = arc.get("source")
        tgt = arc.get("target")
        if src and tgt:
            arcs.append((src, tgt))

    return all_transitions, visible_transitions, places, arcs


def read_hierarchy_csv(csv_path):
    hierarchy = {}
    global_start_time = ""

    abs_path = os.path.abspath(csv_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Hierarchy CSV not found: {abs_path}")

    with open(abs_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            obj = (row.get("object") or "").strip()
            if not obj:
                continue

            generate = [x.strip() for x in (row.get("generate") or "").split(";") if x.strip()]
            generator_by = [x.strip() for x in (row.get("generator_by") or "").split(";") if x.strip()]
            start_timestamp = (row.get("start_timestamp") or "").strip()

            n_objects_raw = (row.get("n_objects") or "").strip()
            n_objects= int(n_objects_raw) if n_objects_raw else None
            hierarchy[obj] = {
                "n_objects": n_objects,
                "generate": generate,
                "generator_by": generator_by,
            }

            if not global_start_time and not generator_by and start_timestamp:
                global_start_time = start_timestamp

    return hierarchy, global_start_time


def build_ordered_transitions(all_transitions, places, arcs):
    place_out = defaultdict(list)
    trans_out = defaultdict(list)
    incoming_nodes = set()

    for src, tgt in arcs:
        incoming_nodes.add(tgt)

        if src in places and tgt in all_transitions:
            if tgt not in place_out[src]:
                place_out[src].append(tgt)
        elif src in all_transitions and tgt in places:
            if tgt not in trans_out[src]:
                trans_out[src].append(tgt)

    start_places = [p for p in places if p not in incoming_nodes]
    if not start_places:
        start_places = sorted(places)

    visited_places = set()
    visited_transitions = set()
    order = []
    queue = deque(sorted(start_places))

    while queue:
        place = queue.popleft()

        if place in visited_places:
            continue
        visited_places.add(place)

        for trans in place_out.get(place, []):
            if trans not in visited_transitions:
                visited_transitions.add(trans)
                order.append(trans)

            for next_place in trans_out.get(trans, []):
                if next_place not in visited_places:
                    queue.append(next_place)

    for tid in all_transitions:
        if tid not in visited_transitions:
            order.append(tid)

    ordered_names = [all_transitions[tid] for tid in order]
    return order, ordered_names


def build_probability(all_transitions, places, arcs):
    place_to_transitions = defaultdict(set)

    for src, tgt in arcs:
        if src in places and tgt in all_transitions:
            place_to_transitions[src].add(tgt)

    probability = {}
    for outs in place_to_transitions.values():
        if len(outs) > 1:
            for t in outs:
                probability[all_transitions[t]] = ""

    return probability


def get_object_name_from_path(pnml_path):
    base = os.path.splitext(os.path.basename(pnml_path))[0]
    return base.replace("_objects", "")


def build_object_template(pnml_path, hierarchy):
    all_transitions, visible_transitions, places, arcs = parse_pnml(pnml_path)

    object_name = get_object_name_from_path(pnml_path)
    obj_cfg = hierarchy.get(object_name, {})
    n_objects = obj_cfg.get("n_objects")
    generate = obj_cfg.get("generate", [])
    generator_by = obj_cfg.get("generator_by", [])

    ordered_ids, ordered_names = build_ordered_transitions(all_transitions, places, arcs)

    ordered_visible_names = [
        all_transitions[tid]
        for tid in ordered_ids
        if tid in visible_transitions
    ]

    processing_time = {
        #DEFAULT VALUES
        name: {"name": "uniform", "parameters": {"low": 0, "high": 0}}
        for name in ordered_visible_names
    }

    resource_role = f"Role {object_name}"

    resource_table = {
        name: resource_role
        for name in ordered_visible_names
    }

    probability_raw = build_probability(all_transitions, places, arcs)
    probability = {
        name: "AUTO"
        for name in ordered_names
        if name in probability_raw
    }
    #DEFAULT VALUES

    inter_trigger_timer = (
        {}
        if generator_by
        else {"type": "distribution", "name": "uniform", "parameters": {"low":0, "high": 0}}
    )
    #DEFAULT VALUES

    obj_dict = {
        **({"n_objects": n_objects} if not generator_by and n_objects is not None else {}),
        #"n_objects": n_objects,
        "path_petrinet": pnml_path,
        "interTriggerTimer": inter_trigger_timer,
        "processing_time": processing_time,
        "waiting_time": {},
        "resource": {
            resource_role: {
                #"resources": [f"{object_name}_resource_{i+1}" for i in range(n_objects or 0)],
                "resources": [f"{object_name}1", f"{object_name}2", f"{object_name}3"],
                "calendar": {
                    "days": [0,1,2,3,4,5,6],
                    "hour_min": 0,
                    "hour_max": 23,
                }
            }
        },
        "resource_table": resource_table,
        "probability": probability,
        "generator_by": generator_by,
        "generate": generate,
        "task_generator": {},
        "object_constraints": {},
        "create_relationship": {},
        "destroy_relationship": {}
    }

    return {object_name: obj_dict}


def build_per_object_template(folder_path, hierarchy_csv_path):
    hierarchy, global_start_time = read_hierarchy_csv(hierarchy_csv_path)
    objects = {}

    for file in os.listdir(folder_path):
        if file.endswith(".pnml"):
            path = os.path.join(folder_path, file)
            objects.update(build_object_template(path, hierarchy))

    return {
        "start_simulation": global_start_time,
        "objects": objects
    }

def dumps_compact_lists(obj, indent=4, level=0):
    sp = " " * (indent * level)
    nxt = " " * (indent * (level + 1))

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = []
        for key, value in obj.items():
            items.append(f'{nxt}{json.dumps(key)}: {dumps_compact_lists(value, indent, level + 1)}')
        return "{\n" + ",\n".join(items) + "\n" + sp + "}"

    if isinstance(obj, list):
        if not obj:
            return "[]"

        # Put lists of simple values on one line
        if all(not isinstance(x, (dict, list)) for x in obj):
            return "[" + ", ".join(json.dumps(x) for x in obj) + "]"

        # Pretty-print nested lists
        items = [f"{nxt}{dumps_compact_lists(x, indent, level + 1)}" for x in obj]
        return "[\n" + ",\n".join(items) + "\n" + sp + "]"

    return json.dumps(obj)

if __name__ == "__main__":
    folder = "petrinet"
    hierarchy_csv = "hierarchy.csv"

    result = build_per_object_template(folder, hierarchy_csv)

   
    #with open("full_from_hierarchy.json", "w", encoding="utf-8") as f:
    #    json.dump(result, f, indent=4)

    with open("full_from_hierarchy.json", "w", encoding="utf-8") as f:
        f.write(dumps_compact_lists(result, indent=4))
    print("multi-object simulation file generated")