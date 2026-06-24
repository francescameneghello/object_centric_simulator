from pathlib import Path
import glob
import os
import xml.etree.ElementTree as ET
import pm4py
from pm4py.algo.analysis.woflan import algorithm as woflan
from pm4py.visualization.petri_net import visualizer as pn_visualizer
import argparse
import json
from collections import defaultdict, deque
import re
import yaml


def bpmn_to_pnml(file_path, output_folder):
    """Transforms a BPMN file to PNML and verifies its initial soundness."""
    bpmn_graph = pm4py.read_bpmn(file_path)
    net, im, fm = pm4py.convert_to_petri_net(bpmn_graph)

    is_sound = woflan.apply(net, im, fm, parameters={woflan.Parameters.RETURN_ASAP_WHEN_NOT_SOUND: True, woflan.Parameters.PRINT_DIAGNOSTICS: False, woflan.Parameters.RETURN_DIAGNOSTICS: False})

    if not is_sound: 
        print(f"Petri net derived from {file_path} is not sound.")
        return None
    pnml_path = str(Path(output_folder) / f"{Path(file_path).stem}.pnml")
    pm4py.write_pnml(net, im, fm, pnml_path)
    return pnml_path

def rename_petrinet(input_pnml, output_pnml):
    """Renames elements in the PNML and ensures it remains sound."""
    tree = ET.parse(input_pnml)
    root = tree.getroot()

    # Remove namespace for easier parsing
    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]

    id_map = {}
    place_counter = 1
    tau_counter = 1

    # 1. Rename places
    for place in root.iter("place"):
        if "id" not in place.attrib:
            continue
        old_id = place.attrib["id"]
        if old_id in ["source", "sink"]:
            continue

        new_id = f"place_{place_counter}"
        place_counter += 1
        id_map[old_id] = new_id
        place.attrib["id"] = new_id

        name = place.find("name")
        if name is not None:
            text = name.find("text")
            if text is not None:
                text.text = new_id

    # 2. Rename transitions
    for trans in root.iter("transition"):
        old_id = trans.attrib["id"]
        name_text = None
        name = trans.find("name")
        if name is not None:
            text = name.find("text")
            if text is not None:
                name_text = text.text

        toolspecific = trans.find("toolspecific")

        # 2.a Invisible transitions
        if toolspecific is not None and toolspecific.attrib.get("activity") == "$invisible$":
            new_id = f"tau_{tau_counter}"
            tau_counter += 1
            id_map[old_id] = new_id
            trans.attrib["id"] = new_id
            if name is not None: 
                text = name.find("text")
                if text is not None:
                    text.text = new_id
        # 2.b Activities
        else:
            if name_text is None:
                continue
            new_id = f"{name_text}"
            id_map[old_id] = new_id
            trans.attrib["id"] = new_id

    # 3. Update arcs
    for arc in root.iter("arc"):
        source = arc.attrib["source"]
        target = arc.attrib["target"]
        if source in id_map:
            arc.attrib["source"] = id_map[source]
        if target in id_map:
            arc.attrib["target"] = id_map[target]

    # 4. Update markings
    for place in root.iter("place"):
        if "idref" in place.attrib:
            ref = place.attrib["idref"]
            if ref in id_map:
                place.attrib["idref"] = id_map[ref]

    # 5. Check post-rename soundness using a temporary file
    temp_pnml = output_pnml.replace('.pnml', '_temp.pnml')
    tree.write(temp_pnml, encoding="utf-8", xml_declaration=True)
    
    net, im, fm = pm4py.read_pnml(temp_pnml)
    is_sound = woflan.apply(net, im, fm, parameters={woflan.Parameters.RETURN_ASAP_WHEN_NOT_SOUND: True, woflan.Parameters.PRINT_DIAGNOSTICS: False, woflan.Parameters.RETURN_DIAGNOSTICS: False}
    )

    if is_sound:
        os.replace(temp_pnml, output_pnml)
        print("PNML successfully rewritten to:", output_pnml)
        return True
    else: 
        if os.path.exists(temp_pnml):
            os.remove(temp_pnml)
        print("Renaming resulted in an unsound Petri net.")
        return False

def visualize_petrinet(input_pnml):
    """Generates and saves the layout image."""
    net, im, fm = pm4py.read_pnml(input_pnml)
    gviz = pn_visualizer.apply(net, im, fm, variant=pn_visualizer.Variants.WO_DECORATION, parameters={'debug': True})
    pn_visualizer.save(gviz, input_pnml.replace(".pnml", ".png"))
    print("Figures saved (.png)")
    
    
### From pnml + spec to produce json file 
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


def read_specifications(spec_path):
    abs_path = os.path.abspath(spec_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Specification file not found: {abs_path}")

    with open(abs_path, 'r', encoding="utf-8") as f:
        data = json.load(f) 
        
    if data is None: 
        raise ValueError(f"Specification file is empty or invalid: {abs_path}")
        
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
    return os.path.splitext(os.path.basename(pnml_path))[0].replace("_objects", "")


def build_object_template(pnml_path, specifications, experiment_root):
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
        "path_petrinet": os.path.join("petrinet", os.path.basename(pnml_path)),
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


def build_per_object_template(folder_path, specifications_path, experiment_root):
    specifications, global_start_time = read_specifications(specifications_path)
    objects = {}

    for file in os.listdir(folder_path):
        if file.endswith(".pnml"):
            path = os.path.join(folder_path, file)
            objects.update(build_object_template(path, specifications, experiment_root))

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

def get_input_mode_and_files(bpmn_dir, pnml_dir):
    """Decides whether to use BPMN or existing PNML files."""
    bpmn_files = list(bpmn_dir.glob("*.bpmn")) if bpmn_dir.exists() else []
    pnml_files = list(pnml_dir.glob("*.pnml")) if pnml_dir.exists() else []

    if bpmn_files:
        return "bpmn", bpmn_files
    return "pnml", pnml_files


def process_bpmn_folder(bpmn_files, pnml_dir):
    pnml_dir.mkdir(exist_ok=True, parents=True)

    for file_path in bpmn_files:
        print(f"\nProcessing BPMN: {file_path}")

        pnml_path = bpmn_to_pnml(str(file_path), str(pnml_dir))
        if pnml_path is None:
            print("Stopped execution due to unsound conversion.")
            return False

        if not rename_petrinet(pnml_path, pnml_path):
            print("Stopped execution due to unsound renaming.")
            return False

        visualize_petrinet(pnml_path)

    return True


def process_pnml_folder(pnml_files):
    for file_path in pnml_files:
        print(f"\nProcessing PNML: {file_path}")

        if not rename_petrinet(str(file_path), str(file_path)):
            print("Stopped execution due to unsound renaming.")
            return False

        visualize_petrinet(str(file_path))

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_name")
    args = parser.parse_args()
    
    project_root = Path(__file__).resolve().parent
    experiment_dir = project_root / "experiments" / args.experiment_name     
    if not experiment_dir.exists():
        raise FileNotFoundError(
            f"Experiment folder '{args.experiment_name}' does not exist in {experiment_dir.parent}"
        )
    
    bpmn_dir = experiment_dir / "bpmn"
    pnml_dir = experiment_dir / "petrinet"
    spec_path = experiment_dir / "specifications.json"
    output_json = experiment_dir / "input.json"
    
    bpmn_files = list(bpmn_dir.glob("*.bpmn")) if bpmn_dir.exists() else []
    pnml_files = list(pnml_dir.glob("*.pnml")) if pnml_dir.exists() else []
    
    mode, files = get_input_mode_and_files(bpmn_dir, pnml_dir)
    
    if not files:
        raise FileNotFoundError(
            f"No BPMN files found in '{bpmn_dir}' and no PNML files found in '{pnml_dir}'."
        )

    print(f"Detected mode: {mode}")

    if mode == "bpmn":
        ok = process_bpmn_folder(files, pnml_dir)
    else:
        ok = process_pnml_folder(files)

    if not ok:
        print("Pipeline stopped due to errors.")
        exit(1)
    
    if spec_path.exists():
        result = build_per_object_template(str(pnml_dir), str(spec_path), str(experiment_dir))
        
        with open(output_json, "w", encoding="utf-8") as f:
            f.write(dumps_compact_lists(result))
        print(f"Full JSON template successfully written to: {output_json}")
    else: 
        print(f"Specifications file not found: {spec_path}")