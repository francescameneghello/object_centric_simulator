import os
import json
import csv
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
import re
import json


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


def read_specifications(json_path):
    abs_path = os.path.abspath(json_path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(
            f"JSON specifications not found: {abs_path}"
        )

    with open(abs_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    specifications = data.get("objects", {})
    global_start_time = data.get("start_simulation", "")

    return specifications, global_start_time


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


def build_object_template(pnml_path, specifications):
    all_transitions, visible_transitions, places, arcs = parse_pnml(pnml_path)

    object_name = get_object_name_from_path(pnml_path)
    obj_cfg = specifications.get(object_name, {})
    
    n_objects = obj_cfg.get("n_objects")
    generator_by = obj_cfg.get("generator_by", [])
    
    ordered_ids, ordered_names = build_ordered_transitions(all_transitions, places, arcs)

    ordered_visible_names = [
        all_transitions[tid]
        for tid in ordered_ids
        if tid in visible_transitions
    ]

    resource_role = f"Role {object_name}"

    probability_raw = build_probability(all_transitions, places, arcs)
    probability = {
        name: "AUTO"
        for name in ordered_names
        if name in probability_raw
    }

    obj_dict = {
        **({"n_objects": n_objects} if not generator_by and n_objects is not None else {}),
        "path_petrinet": pnml_path,
        "interTriggerTimer": (
            {}
            if generator_by
            else {"type": "distribution", "name": "uniform", "parameters": {"low": 1, "high": 10}}
        ),
        "processing_time": {
            name: {"name": "uniform", "parameters": {"low": 1, "high": 5}}
            for name in ordered_visible_names
        },
        "waiting_time": {},
        "resource": {
            resource_role: {
                "resources": [f"{object_name}1", f"{object_name}2", f"{object_name}3"],
                "calendar": {
                    "days": [0,1,2,3,4,5,6],
                    "hour_min": 0,
                    "hour_max": 23,
                }
            }
        },
        "resource_table": {
            name: resource_role
            for name in ordered_visible_names
        },
        "probability": probability,
        "generator_by": generator_by,
        "generate": obj_cfg.get("generate", []),
        "task_generator": obj_cfg.get("task_generator", {}),                 
        "object_constraints": obj_cfg.get("object_constraints", {}),    
        "create_relationship": obj_cfg.get("create_relationship", {}),     
        "destroy_relationship": obj_cfg.get("destroy_relationship", {})
    }

    return {object_name: obj_dict}


def build_per_object_template(folder_path, specifications_path):
    specifications, global_start_time = read_specifications(specifications_path)
    objects = {}

    for file in os.listdir(folder_path):
        if file.endswith(".pnml"):
            path = os.path.join(folder_path, file)
            objects.update(build_object_template(path, specifications))

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
        # Function to check if a list contains only basic types (strings, ints) 
        # or lists that ONLY contain basic types (like your constraint arrays)
        def is_simple_list(lst):
            for x in lst:
                if isinstance(x, dict):
                    return False
                if isinstance(x, list):
                    # If it's a nested list, verify it doesn't contain deep objects
                    if any(isinstance(y, (dict, list)) for y in x):
                        return False
            return True

        if is_simple_list(obj):
            # This generates standard compact JSON representation for this list
            return json.dumps(obj)

        # If it's a complex list (like a list of objects), pretty-print it across multiple lines
        items = [f"{nxt}{dumps_compact_lists(x, indent, level + 1)}" for x in obj]
        return "[\n" + ",\n".join(items) + "\n" + sp + "]"

    return json.dumps(obj)

if __name__ == "__main__":
    folder = "petrinet"
    specifications_json = "specifications.json"

    result = build_per_object_template(folder, specifications_json)

    with open("full_from_json.json", "w", encoding="utf-8") as f:
        f.write(dumps_compact_lists(result, indent=4))
    print("multi-object simulation file generated")