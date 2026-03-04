import csv
import simpy
import utility
from datetime import datetime, timedelta
from process import SimulationProcess
from object_class import Object
from parameters import Parameters
import sys, getopt
from utility import *
import random
import pm4py
#from inter_trigger_timer import InterTriggerTimer
#from result_analysis import Result
from datetime import timedelta
import warnings
import sys


def setup(env: simpy.Environment, params, i, name, f):
    simulation_process = SimulationProcess(env, params)
    utility.define_folder_output("output/output_{}".format(name))
    writer = csv.writer(f)
    writer.writerow(Buffer(writer).get_buffer_keys())

    ### launch all the independent object
    for obj in params.objects:
        if not params.objects[obj]["generator_by"]:
            n_traces = params.objects[obj]["n_traces"]
            interval = random.randint(0, 600)
            start_simulation_object = params.START_SIMULATION
            for i in range(0, n_traces):
                prefix = Prefix()
                itime = interval
                yield env.timeout(itime)
                time_trace = start_simulation_object + timedelta(seconds=env.now)
                net, im, fm = pm4py.read_pnml(params.objects[obj]["path_petrinet"])
                id= f"{obj}_{i}"
                mailboxes = {id: simpy.FilterStore(env)}
                env.process(Object(id, net, im, params, simulation_process, prefix, 'sequential', writer,
                                  obj, mailboxes).simulation(env))


def run_simulation(path_parameter: str, name: str, n_simulation=1):
    for i in range(0, n_simulation):
        with open("output/output_{}/simulated_log_{}_{}".format(name, name, i) + ".csv", 'w') as f:
            params = Parameters(path_parameter)
            env = simpy.Environment()
            env.process(setup(env, params, i, name, f))
            env.run()
    #result = Result("output_{}".format(NAME), Parameters(PATH_PARAMETERS, N_TRACES))
    #result._analyse()


def main(path_parameter: str, name: str):
    print(path_parameter, name)
    run_simulation(path_parameter, name)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main(path_parameter="../input/input_process_order.json", name="order_process")