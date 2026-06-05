import csv
import simpy
import utility
from datetime import datetime, timedelta
from process import SimulationProcess
from object_class import Object
from parameters import Parameters
import sys, getopt
import numpy as np
from utility import *
import random
import pm4py
from datetime import timedelta
import warnings
import sys


def setup(env: simpy.Environment, params, i, name, f, base_path):
    simulation_process = SimulationProcess(env, params)
    utility.define_folder_output("../analysis/output_log")
    writer = csv.writer(f)
    writer.writerow(Buffer(writer).get_buffer_keys())

    ### launch all the independent object
    for obj in params.objects:
        if not params.objects[obj]["generator_by"]:
            n_objects = params.objects[obj]["n_objects"]
            distribution = params.objects[obj]["interTriggerTimer"]['name']
            parameters = params.objects[obj]["interTriggerTimer"]['parameters']
            
            #PATH addition for the pnml file
            raw_pnml_path = params.objects[obj]["path_petrinet"]
            pnml_path = os.path.normpath(os.path.join(base_path, raw_pnml_path))
            
            start_simulation_object = params.START_SIMULATION
            for i in range(0, n_objects):
                prefix = Prefix()
                parallel_object = utility.ParallelObject()
                interval = getattr(np.random, distribution)(**parameters, size=1)[0]
                itime = interval
                #net, im, fm = pm4py.read_pnml(params.objects[obj]["path_petrinet"])
                net, im, fm = pm4py.read_pnml(pnml_path)
                id = f"{obj}_{i}"
                obj_class = Object(id, net, im, params, simulation_process, prefix, 'sequential', writer, obj, parallel_object)
                simulation_process.add_object(obj_class, obj, id)
                env.process(obj_class.simulation(itime, env))


def run_simulation(path_parameter: str, name: str, n_simulation=1):
    base_path = os.path.dirname(os.path.abspath(path_parameter))
    for i in range(0, n_simulation):
        with open("../analysis/output_log/simulated_log_{}_{}".format(name, i) + ".csv", 'w') as f:
            params = Parameters(path_parameter)
            env = simpy.Environment()
            setup(env, params, i, name, f, base_path)
            env.run()

def main(path_parameter: str, name: str):
    print(path_parameter, name)
    run_simulation(path_parameter, name, n_simulation=1)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    script_dir = os.path.dirname(__file__)
    #json_path = os.path.join(script_dir, "../input/full_from_spec.json")
    json_path = os.path.join(script_dir, "../input/input_process_order_toy.json")
    #main(path_parameter=json_path, name="full_from_spec")
    main(path_parameter=json_path, name="process_order_toy")