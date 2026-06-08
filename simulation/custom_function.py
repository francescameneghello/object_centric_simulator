'''
This file contains all the customizable functions, which the user can define,
and which are called by the simulator in the specific steps.

The following table describes the case and inter-case features that can be
used as input from a predictive model.

| Feature      | Description  |
|:------------:|:-------------------------- |
| id_case | Case id of the object to which the event belongs. |
| activity | Name of the activity being executed. |
| enabled_time | Timestamp of when the activity requests the role to be executed. |
| start_time |  Timestamp of when the activity starts to run.   |
| end_time |   Timestamp of when the activity ends to run.    |
| role |   Designated role to perform the activity.   |
| resource |  Role resource available to perform the activity.   |
| wip_wait | Work-in-progress measure at the time the activity is waiting for execution|
| wip_start |  Represents the number of objects running in the simulation once an available resource is obtained to run the activity. |
| wip_end | Represents the number of objects running in the simulation at the end of the activity execution. |
| wip_activity |  Represents the number of events running in the simulation that perform the same activity, once an available resource is obtained.   |
| ro_total |    The percentage of occupancy in terms of resources in use for the roles defined in the simulation.   |
| ro_single |   The percentage of occupancy in terms of resources in use for the role defined for the next activity.     |
| queue |  Represents the length of the queue for the required resource.  |
| prefix |  List of activities already performed.  |
| relationships |  Set of objects related to the event.  |
| attribute_object |  Attributes defined for the object.      |
| attribute_event |  Attributes defined for the next event to be executed.   |

'''

from statsmodels.tsa.ar_model import AutoRegResults
from utility import Buffer
import random
import pickle
from datetime import datetime
import os


def object_function_attribute(object_type: str):
    """
        Function to add one or more attributes to each object type.
        Each object instance can get a different value for the defined attribute(s). For example, we added a "Price" attribute to the "item" object type.
    """
    if object_type == 'item':
        return {"Price": random.randint(50, 1000)}
    if object_type == 'order':
        return {"City": random.choice(["Bolzano", "Milano", "Roma"])}
    else:
        return {}
    
def find_objects(process, object_id):
    for object_type, objects in process.existing_objects.items():
        if object_id in objects:
            return objects[object_id]
    return None

def custom_cardinality_rule(process, current_object_id, available_items):
    """
        Custom function that defines the shipment characteristics. Since items are liked to orders, they inherity the attribute city. 
        The user can define a custom rule to decide which items to ship together, for example, by grouping the items by city and choosing the largest group.
        Then truck inherits the city attribute of the items, and the function returns the set of items to ship together.
        When truck loads again other items, the function is called again, and the city attribute of the truck can be updated with the city of the new items.
    """
    min_same_city = 2  # Example parameter for the custom rule
    items_dict = process.get_specific_type("item")
    truck = find_objects(process, current_object_id)
    
    if truck is None: 
        return False, set()    

    city_groups = {}

    for item_id in available_items:
        if item_id not in items_dict:
            continue

        item_obj = items_dict[item_id]
        city = item_obj._attribute.get("City")

        if city is None:
            continue

        city_groups.setdefault(city, set()).add(item_id)

    valid_groups = {
        city: ids for city, ids in city_groups.items() 
        if len(ids) >= min_same_city
    }

    if not valid_groups:
        return False, set()
    
    best_city = max(valid_groups, key=lambda city: len(valid_groups[city]))

    # choose the largest group
    best_group = valid_groups[best_city]
    
    truck._attribute["City"] = best_city

    return True, best_group


# def custom_arrivals_time(case, previous):
#     """
#     Function to define a new arrival of a trace. 
#     The input parameters are the case id number and 
#     the start timestamp of the previous trace.
#     For example, we used an AutoRegression model 
#     for the *arrivals example*.
#     """
#     loaded = AutoRegResults.load('example/example_arrivals/arrival_AutoReg_model.pkl')
#     return loaded.predict(case+1, case+1)[0]


def custom_processing_time(buffer: Buffer):
    """
    Define the processing time of the activity (return the duration in seconds).
    Example of features that can be used to predict:

    ```json
            {
                "id_case": order_92,
                "activity": "Check out",
                "enabled_time": "2026-01-01 09:48:17",
                "start_time": "2026-01-01 09:10:13",
                "end_time": "2026-01-02 05:19:18",
                "role": "Role 1 order",
                "resource": "Sue",
                "wip_wait": 167,
                "wip_start": 483,
                "wip_end": 483,
                "wip_activity": 1,
                "ro_total": "[0.0, 1.0, 0.0, 1.0, 0.0]",
                "ro_single": 1.0,
                "queue": 151,
                "prefix": "['Place Order', 'Check out']",
                "relationships": "{'item_92_0', 'item_92_1'}",
                "attribute_object": {},
                "attribute_event": {}
            }
    ```
    """
    buffer.print_values()
    input_feature = list()
    input_feature.append(buffer.get_feature("wip_start"))
    input_feature.append(buffer.get_feature("wip_activity"))
    input_feature.append(buffer.get_feature("start_time").weekday())
    input_feature.append(buffer.get_feature("start_time").hour)
    loaded_model = pickle.load(
        open(os.getcwd()+'/example/example_process_times/processing_time_random_forest.pkl', 'rb'))
    y_pred_f = loaded_model.predict([input_feature])
    return int(y_pred_f[0])


def custom_waiting_time(buffer: Buffer):
    """ Define the waiting time of the activity (return the duration in seconds).
    Example of features that can be used to predict:
    ```json
    {
        "id_case": 15,
        "activity": "A_PARTLYSUBMITTED",
        "enabled_time": "None",
        "start_time": "None",
        "end_time": "None",
        "role": "Role 2",
        "resource": "None",
        "wip_wait": 21,
        "wip_start": -1,
        "wip_end": -1,
        "wip_activity": 1,
        "ro_total": [0.5, 1],
        "ro_single": 1,
        "queue": 13,
        "prefix": ["A_SUBMITTED"],
        "attribute_case": {"AMOUNT": 18207},
        "attribute_event": {"bank_branch": "Eindhoven"}

    }
    ```
    """
    return 0


def custom_decision_mining(buffer: Buffer, objects_related: list, possible_transitions: list):
    """
    Function to define the next activity from a decision point in the Petri net model.

    Example of features that can be used to predict:
    ```json
        {
            "id_case": item_152_1,
            "activity": "Pick Item",
            "enabled_time": "2026-01-02 04:30:16",
            "start_time": "2026-01-02 04:30:16",
            "end_time": "2026-01-02 04:32:37",
            "role": "Role 2 item",
            "resource": "Sue",
            "wip_wait": 472,
            "wip_start": 472,
            "wip_end": 474,
            "wip_activity": 2,
            "ro_total": "[0.0, 1.0, 0.0, 0.0, 0.5]",
            "ro_single": 0.5,
            "queue": 0,
            "prefix": "['Select', 'Pick Item']",
            "relationships": {'order_152'}
            "attribute_object": {'Price': 58},
            "attribute_event": {}

        }
    ```
    """
    
    total_cost_order = 0
    for obj in objects_related:
        total_cost_order += obj._attribute["Price"]
    if total_cost_order == 0:
        return 0 ## CLose Order
    elif total_cost_order > 1000:
        return 2
    else:
        return 1