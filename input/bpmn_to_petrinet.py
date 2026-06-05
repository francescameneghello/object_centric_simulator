import glob
import os
import xml.etree.ElementTree as ET
import pm4py
from pm4py.algo.analysis.woflan import algorithm as woflan
from pm4py.visualization.petri_net import visualizer as pn_visualizer


def bpmn_to_pnml(file_path, output_folder):
    """Transforms a BPMN file to PNML and verifies its initial soundness."""
    bpmn_graph = pm4py.read_bpmn(file_path)
    net, im, fm = pm4py.convert_to_petri_net(bpmn_graph)

    is_sound = woflan.apply(net, im, fm, parameters={woflan.Parameters.RETURN_ASAP_WHEN_NOT_SOUND: True, woflan.Parameters.PRINT_DIAGNOSTICS: False, woflan.Parameters.RETURN_DIAGNOSTICS: False})

    if not is_sound: 
        print(f"Petri net derived from {file_path} is not sound.")
        return None

    pnml_path = os.path.join(output_folder, os.path.basename(file_path).replace('.bpmn', '.pnml'))
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
            if name is not None and text is not None:
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
    """Generates and saves the debug layout image."""
    net, im, fm = pm4py.read_pnml(input_pnml)
    gviz = pn_visualizer.apply(net, im, fm, variant=pn_visualizer.Variants.WO_DECORATION, parameters={'debug': True})
    pn_visualizer.save(gviz, input_pnml.replace(".pnml", ".png"))
    print("Figures saved (.png)")


if __name__ == "__main__":
    in_folder = 'bpmn'
    output_folder = 'petrinet'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    pattern = os.path.join(in_folder, '*.bpmn')

    for file_path in glob.glob(pattern):
        print(f"\nProcessing: {file_path}")

        # 1. Transform step
        pnml_path = bpmn_to_pnml(file_path, output_folder)
        if pnml_path is None:
            print("Stopped execution due to unsound network conversion.")
            break

        # 2. Rename step
        rename_success = rename_petrinet(pnml_path, pnml_path)
        if not rename_success:
            print("Stopped execution due to unsound renaming layout.")
            break

        # 3. Visualize step
        visualize_petrinet(pnml_path)