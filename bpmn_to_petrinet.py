import pm4py
from pm4py.algo.analysis.woflan import algorithm as woflan

PATH_BPMN = 'input/item_objects.bpmn'

bpmn_graph = pm4py.read_bpmn(PATH_BPMN)
net, im, fm = pm4py.convert_to_petri_net(bpmn_graph)

pm4py.write_pnml(net, im, fm, "input/item_objects.pnml")
pm4py.view_petri_net(net, im, fm)
pm4py.save_vis_petri_net(net, im, fm, "input/item_objects.png")

is_sound = woflan.apply(net, im, fm, parameters={woflan.Parameters.RETURN_ASAP_WHEN_NOT_SOUND: True, woflan.Parameters.PRINT_DIAGNOSTICS: False, woflan.Parameters.RETURN_DIAGNOSTICS: False})
print('SOUND: ', is_sound)