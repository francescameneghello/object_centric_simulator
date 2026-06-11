import csv
import simpy
import utility
from datetime import datetime, timedelta
from parameters import Parameters
import sys, getopt
import numpy as np
from utility import *
import random
import pm4py
import warnings
import sys
import os 
import argparse
from pathlib import Path


def setup(env: simpy.Environment, params, i, name, f, experiments_root):
    #these imports must stay inside due to the different location of custom_function in a different folder with respect to the core of the simulation
    from process import SimulationProcess
    from object_class import Object
    from inter_trigger_timer import InterTriggerTimer
    
    simulation_process = SimulationProcess(env, params)
    
    output_dir = experiments_root.parent.parent / "analysis" / "experiments" / name / "output_log"
    os.makedirs(output_dir, exist_ok=True)
    utility.define_folder_output(output_dir)
    
    writer = csv.writer(f)
    writer.writerow(Buffer(writer).get_buffer_keys())

    ### launch all the independent object
    for obj in params.objects:
        if not params.objects[obj]["generator_by"]:
            n_objects = params.objects[obj]["n_objects"]
            distribution = params.objects[obj]["interTriggerTimer"]['name']
            parameters = params.objects[obj]["interTriggerTimer"]['parameters']
                       
            pnml_path = params.objects[obj]["path_petrinet"]      
            if not os.path.isabs(pnml_path):
                pnml_path = os.path.join(experiments_root, pnml_path)

            if not os.path.exists(pnml_path):
                raise FileNotFoundError(f"PNML not found: {pnml_path}")

            start_simulation_object = params.START_SIMULATION
            for i in range(0, n_objects):
                prefix = Prefix()
                parallel_object = utility.ParallelObject()
                #interval = getattr(np.random, distribution)(**parameters, size=1)[0]
                #itime = interval
                timer_config = params.objects[obj]["interTriggerTimer"]
                inter_trigger_timer = InterTriggerTimer(timer_config, simulation_process, params.START_SIMULATION)
                itime = inter_trigger_timer.get_next_arrival(env, obj)
                net, im, fm = pm4py.read_pnml(pnml_path)
                id = f"{obj}_{i}"
                obj_class = Object(id, net, im, params, simulation_process, prefix, 'sequential', writer, obj, parallel_object)
                simulation_process.add_object(obj_class, obj, id)
                env.process(obj_class.simulation(itime, env))
                


def run_simulation(path_parameter: str, name: str, n_simulation=1):    
    project_root = Path(__file__).resolve().parent.parent
    experiments_root = project_root / "input" / "experiments"
    
    for i in range(0, n_simulation):
        output_dir = project_root / "analysis" / "experiments" / name / "output_log"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = output_dir / f"simulated_log_{name}_{i}.csv"
        with open(log_file, 'w') as f:
            params = Parameters(path_parameter)
            env = simpy.Environment()
            setup(env, params, i, name, f, experiments_root)
            env.run()

def main(path_parameter: str, name: str):
    print(path_parameter, name)
    run_simulation(path_parameter, name, n_simulation=1)

if __name__ == "__main__":
    warnings.filterwarnings("ignore")

    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_name")  # order2deliverly, hospital, etc.
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    experiment_dir = script_dir.parent / "input" / "experiments" / args.experiment_name

    sys.path.insert(0, str(experiment_dir))

    json_files = [
        f for f in experiment_dir.glob("*.json")
        if f.name != "specifications.json"
    ]

    if len(json_files) != 1:
        raise ValueError(
            f"Expected exactly one simulation JSON file in {experiment_dir}, "
            f"found {len(json_files)}: {[f.name for f in json_files]}"
        )

    json_path = json_files[0]
    # json_files = list(experiment_dir.glob("*.json"))
    # if len(json_files) != 1:
    #     raise ValueError(f"Expected exactly one JSON file in {experiment_dir}, found {len(json_files)}")

    # json_path = json_files[0]

    main(path_parameter=str(json_path), name=args.experiment_name)