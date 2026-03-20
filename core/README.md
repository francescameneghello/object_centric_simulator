# Simulating Dynamic Relationships in Object-Centric Processes

## Installation guide

To execute this code, use **Python 3.10** and install the following main packages:

* scikit-learn==1.2.1
* scipy==1.11.2
* simpy==4.0.1
* pm4py==2.7.5.2
* statsmodels==0.14.0
* pandas==1.5.3

or you can use the configuration file called requirements.txt to install all specified package versions.

```shell
pip install -r requirements.txt
```

## Getting Started

Once the packages are installed, <ins>inside the core folder</ins> you can run one or more simulations by specifying the following parameters in *main* function of *run_simulation.py*.
* `path_parameter`: specify the path to the simulation parameter file, in *json* format
* `name`: name of the process to run
* `n_simulation`: specify the total number of simulation to run

```shell
python run_simulation.py
```


## Input files

This document explains how to configure and fix parameters for each object type in the process, for instance *truck, order, item* of the motivating example.

"start_simulation": "YYYY-MM-DD HH:MM:SS" : global start of simulation

"<object_name>": {
    "n_objects": <int>,
    "path_petrinet": "<path>",
    "interTriggerTimer": {...},
    "processing_time": {...},
    "waiting_time": {...},
    "resource": {...},
    "resource_table": {...},
    "probability": {...},
    "generator_by": [...],
    "task_generator": {...},
    "generate": [...],
    "object_constraints": {...},
    "create_relation_ship": {...},
    "destroy_relation_ship": {...}
}

This block defines all configuration parameters for a simulation object, including its creation, timing, resources, behavior, and relationships with other objects; detailed examples and exact usage can be found in the files inside the input_folder.