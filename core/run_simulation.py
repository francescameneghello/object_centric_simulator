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
#from inter_trigger_timer import InterTriggerTimer
from datetime import timedelta
import warnings
import sys


def setup(env: simpy.Environment, params, i, name, f):
    simulation_process = SimulationProcess(env, params)
    utility.define_folder_output("output")
    writer = csv.writer(f)
    writer.writerow(Buffer(writer).get_buffer_keys())

    ### launch all the independent object
    for obj in params.objects:
        if not params.objects[obj]["generator_by"]:
            n_objects = params.objects[obj]["n_objects"]
            distribution = params.objects[obj]["interTriggerTimer"]['name']
            parameters = params.objects[obj]["interTriggerTimer"]['parameters']
            start_simulation_object = params.START_SIMULATION
            for i in range(0, n_objects):
                prefix = Prefix()
                interval = getattr(np.random, distribution)(**parameters, size=1)[0]
                itime = interval
                yield env.timeout(0)
                net, im, fm = pm4py.read_pnml(params.objects[obj]["path_petrinet"])
                id = f"{obj}_{i}"
                obj_class = Object(id, net, im, params, simulation_process, prefix, 'sequential', writer, obj)
                simulation_process.add_object(obj_class, obj, id)
                env.process(obj_class.simulation(itime, env))


def run_simulation(path_parameter: str, name: str, n_simulation=1):
    for i in range(0, n_simulation):
        with open("output/simulated_log_{}_{}".format(name, i) + ".csv", 'w') as f:
            params = Parameters(path_parameter)
            env = simpy.Environment()
            env.process(setup(env, params, i, name, f))
            env.run()

def main(path_parameter: str, name: str):
    print(path_parameter, name)
    run_simulation(path_parameter, name, n_simulation=1)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main(path_parameter="../input/input_process_order_90.json", name="process_order_90")