from datetime import datetime, timedelta
import simpy
import pm4py
import random
from process import SimulationProcess
from pm4py.objects.petri_net import semantics
from parameters import Parameters
from utility import Prefix
from simpy.events import AnyOf, AllOf, Event
import numpy as np
import copy
import csv
from utility import Buffer, ParallelObject
from importlib import import_module


class Object(object):

    def __init__(self, id: str, net: pm4py.objects.petri_net.obj.PetriNet, am: pm4py.objects.petri_net.obj.Marking,
                 params: Parameters, process: SimulationProcess, prefix: Prefix, type: str, writer: csv.writer,
                 name_object: str, parallel_object: ParallelObject, name_exp: str, type_log= 'ocel', father=None, values_buffer=None):
        self._id = id
        self._process = process
        self._start_time = params.START_SIMULATION
        self._general_params = params
        self._net = net
        self._am = am
        self.prefix = prefix
        self._type = type
        self._name_object = name_object
        self._name_exp = name_exp
        self._custom = import_module(f"input.experiments.{self._name_exp}.custom_function")
        self._object_params = params.objects[name_object]
        if type == 'sequential':
            self.see_activity = False
        else:
            self.see_activity = True
        self._writer = writer
        self._buffer = Buffer(writer, [])
        self._id_object = 0
        self._father = father
        self._last_activity = None
        self._attribute = self._custom.object_function_attribute(self._name_object)
        if father is not None and hasattr(father, "_attribute") and father._attribute:
            self._attribute.update(copy.deepcopy(father._attribute))
        self._buffer.set_feature("attribute_object", self._attribute)
        self._parallel_object = parallel_object
        self._type_log = type_log

    def _delete_places(self, places):
        delete = []
        for place in places:
            for p in self._net.places:
                if str(place) in str(p.name):
                    delete.append(p)
        return delete

    def _sample_distribution(self, distribution, parameters):
        n_sample = getattr(np.random, distribution)(**parameters, size=1)[0]
        if n_sample < 0:
            print("WARNING: Negative value", n_sample)
            n_sample = 0
        return int(n_sample)

    def check_generator(self, env, next_act):
        """
        Method used to check whether the transition next_act emits an object.
        If it does, the method generates *n* corresponding objects according to the parameters specified in the **input.json file**.
        For instance:
        ```json
        "Place Order": {
          "obj": "item",
          "name": "uniform",
          "parameters": {
            "low": 2,
            "high": 3
          }
        }
        ```
        """
        if next_act in self._object_params["task_generator"]:
            name_obj = self._object_params["task_generator"][next_act]["obj"]
            n_obj = self._sample_distribution(self._object_params["task_generator"][next_act]["name"], self._object_params["task_generator"][next_act]["parameters"])
            for i in range(0, n_obj):
                net, im, fm = pm4py.read_pnml(self._general_params.objects[name_obj]["path_petrinet"])
                id = f"{name_obj}_{int(self._id.rsplit('_', 1)[1])}_{self._id_object}"
                obj_class = Object(id, net, im, self._general_params, self._process, Prefix(),
                               'sequential', self._writer, name_obj, parallel_object=ParallelObject(), name_exp=self._name_exp, father=self)
                self._process.add_object(obj_class, name_obj, id)
                self._process.set_relationships(self._id, id)
                env.process(obj_class.simulation(0, env))
                self._id_object += 1


    def check_constraints(self, next_act):
        """
        Checks whether the next transition to be executed has any relationships with transitions of
        other objects. If such relationships exist, the method extracts the corresponding parameters
        from the input.json file.
        For instance:
        ```json
        "Name of the transition": {
            "obj": "item",
            "trans": ["Pick Item", "Remove Item"],
            "card": "All | Any | int | [min, max] | CUSTOM"
        }
        ```
        """

        info = self._object_params["object_constraints"][next_act]

        obj_type = info.get("obj")
        trans_list = info.get("trans", [])
        cardinality = info.get("card", "All")

        proceed = False
        selected_messages = {}

        if next_act in self._object_params.get("create_relationship", {}):
            type_objects = set(self._process._get_specific_type(obj_type).keys())
            picked_messages = {
                (item_id, action, ref)
                for item_id, action, ref in self._process.board.messages
                if action in trans_list
            }

            picked_items = {item_id for item_id, _, _ in picked_messages}
            available = type_objects & picked_items
            matched = type_objects & picked_items

            if isinstance(cardinality, list):
                min_val, max_val = map(int, cardinality)

                if len(available) >= min_val:
                    k = min(len(available), max_val)
                    matched = set(random.sample(list(available), k))
                    selected_messages = {
                        (item_id, action, ref)
                        for item_id, action, ref in picked_messages
                        if item_id in matched
                    }
                    proceed = True
                else: 
                    return False, set()

            elif isinstance(cardinality, int):
                if len(available) >= cardinality:
                    matched = set(random.sample(list(available), cardinality))
                    selected_messages = {
                        (item_id, action, ref)
                        for item_id, action, ref in picked_messages
                        if item_id in matched
                    }
                    proceed = True
                else: 
                    return False, set()

            elif cardinality == "All":
                proceed = matched == type_objects
                selected_messages = picked_messages 

            elif cardinality == "Any":
                proceed = len(matched) >= 1
                selected_messages = {
                    (item_id, action, ref)
                    for item_id, action, ref in picked_messages
                    if item_id in matched
                }
                
            elif cardinality == "CUSTOM":
                proceed, matched = self._custom.custom_cardinality_rule(
                    process=self._process, 
                    current_object_id = self._id,
                    available_objects=available,
                )
                selected_messages = {
                    (item_id, action, ref)
                    for item_id, action, ref in picked_messages
                    if item_id in matched
                }
                
            if proceed:
                for obj in matched:
                    self._process.set_relationships(self._id, obj)

                self._process.board.remove_message(selected_messages)
                return True, matched

            return False, set()

        else:
            # objects currently related
            id_target_object = {
                x for x in self._process.get_relationships(self._id)
                if x.split('_')[0] == obj_type
            }

            picked_messages = {
                (item_id, action, ref)
                for item_id, action, ref in self._process.board.messages
                if action in trans_list and self._id in ref
            }

            picked_items = {item_id for item_id, _, _ in picked_messages}
            matched = id_target_object & picked_items
            
            if id_target_object or picked_items:

                if cardinality == "All":
                    proceed = matched == id_target_object

                elif cardinality == "Any":
                    proceed = len(matched) >= 1

                elif isinstance(cardinality, list):
                    min_val, max_val = map(int, cardinality)
                    proceed = min_val <= len(matched) <= max_val

                elif isinstance(cardinality, int):
                    proceed = len(matched) >= cardinality

            if proceed:
                self._process.board.remove_message(picked_messages)

            return proceed, matched

    def simulation(self, inter_trigger_timer: int, env: simpy.Environment):
        """
            The main function to handle the simulation
        """
        yield env.timeout(inter_trigger_timer)
        transition = self.next_transition(env)
        resource_object = self._process._get_resource_object()
        resource_object_request = resource_object.request() if self._type == 'sequential' else None

        while transition is not None:
            if not self.see_activity and self._type == 'sequential':
                yield resource_object_request
            if type(transition) == list:
                yield AllOf(env, transition)
                am_after = self._parallel_object._get_last_events()
                for d in self._delete_places(self._am):
                    del self._am[d]
                for t in am_after:
                    self._am[t] = 1
                transition = self.next_transition(env)

            if transition and transition.label:  ### next transition to execute
                matched = []
                if transition.label in self._object_params["object_constraints"]:
                    proceed = False
                    while not proceed:
                        proceed, matched = self.check_constraints(transition.label)
                        if not proceed:
                            yield self._process.board.new_message_event

                self._buffer.reset()
                self._buffer.set_feature("obj_id", self._id)
                self._buffer.set_feature("activity", transition.label)
                self._buffer.set_feature("prefix",
                                         self.prefix.get_prefix(self._start_time + timedelta(seconds=env.now)))

                self._attribute = self._custom.update_object_attribute(self._name_object, transition.label, self._attribute)
                self._buffer.set_feature("attribute_object", self._attribute)


                ### call predictor for waiting time
                if transition.label in self._object_params["resource_table"]:
                    resource = self._process._get_resource(self._object_params["resource_table"][transition.label])
                else:
                    raise ValueError('Not resource/role defined for this activity', transition.label)

                self._buffer.set_feature("wip_wait", 0 if type != 'sequential' else resource_object.count-1)
                self._buffer.set_feature("ro_single", self._process.get_occupations_single_role(resource._get_name()))
                self._buffer.set_feature("ro_total", self._process.get_occupations_all_role())
                self._buffer.set_feature("role", resource._get_name())

                ### register event in process ###
                resource_task = self._process._get_resource_event(transition.label)
                self._buffer.set_feature("wip_activity", resource_task.count)

                queue = 0 if len(resource._queue) == 0 else len(resource._queue[-1])
                self._buffer.set_feature("queue", queue)
                self._buffer.set_feature("enabled_time", (self._start_time + timedelta(seconds=env.now)).replace(microsecond=0))

                waiting = self.define_waiting_time(transition.label)
                yield env.timeout(waiting)

                request_resource = resource.request()
                yield request_resource
                single_resource = self._process._set_single_resource(resource._get_name())
                self._buffer.set_feature("resource", single_resource)

                resource_task_request = resource_task.request()
                yield resource_task_request

                ### call predictor for processing time
                self._buffer.set_feature("wip_start", resource_object.count)
                self._buffer.set_feature("ro_single", self._process.get_occupations_single_role(resource._get_name()))
                self._buffer.set_feature("ro_total", self._process.get_occupations_all_role())
                self._buffer.set_feature("wip_activity", resource_task.count)

                stop = resource.to_time_schedule(self._start_time + timedelta(seconds=env.now))
                yield env.timeout(stop)
                self._buffer.set_feature("start_time", (self._start_time + timedelta(seconds=env.now)).replace(microsecond=0))
                duration = self.define_processing_time(transition.label)
                yield env.timeout(duration)

                self._buffer.set_feature("wip_end", resource_object.count)
                self._buffer.set_feature("end_time", (self._start_time + timedelta(seconds=env.now)).replace(microsecond=0))
                self.prefix.add_activity(transition.label)
                self.check_generator(env, transition.label)
                self._last_activity = transition.label

                self._buffer.set_feature("relationships", self._define_relationships().copy())
                if transition.label in self._general_params.channels:
                    if transition.label in self._object_params["destroy_relationship"]:
                        rel = list(self._process.get_relationships(self._id))
                        rel_obj = [x for x in rel if self._object_params["destroy_relationship"][transition.label] in x]
                        for m in rel_obj:
                            self._process.remove_relationships(self._id, m)
                            self._process.board.add_message((self._id, transition.label, m))
                    else:
                        if matched:
                            for m in matched: self._process.board.add_message((self._id, transition.label, m))
                        elif self._father:
                            self._process.board.add_message((self._id, transition.label, self._father._id))
                        else:
                            obj = list(self._process.get_relationships(self._id))
                            rel_obj = [x for x in obj if self._general_params.channels[transition.label] in x]
                            for m in rel_obj:
                                self._process.board.add_message((self._id, transition.label, m))

                self._buffer.print_values()
                resource.release(request_resource)
                self._process._release_single_resource(resource._get_name(), single_resource)
                resource_task.release(resource_task_request)

            self._update_marking(transition)
            transition = self.next_transition(env) if self._am else None

        if self._type == 'parallel':
            self._parallel_object._set_last_events(self._am)
        if self._type == 'sequential':
            self._process._remove_element(self._id)
            self._process._delete_specific_object(self._name_object, self._id)
            resource_object.release(resource_object_request)

    def _define_relationships(self):
        if self._type_log == 'snapshot':
            relationships = self._process._get_all_relationships()
        else:
            relationships = self._process.get_relationships(self._id)
            if self._father:
                relationships.add(self._father._id)
        return relationships if relationships else {}

    def _update_marking(self, transition):
        self._am = semantics.execute(transition, self._net, self._am)

    def _delete_tokens(self, name):
        to_delete = []
        for p in self._am:
            if p.name != name:
                to_delete.append(p)
        return to_delete

    def _check_probability(self, prob):
        """Check if the sum of probabilities is 1
        """
        if sum(prob) != 1:
            print(
                'WARNING: The sum of the probabilities associated with the paths is not 1, to run the simulation we define equal probability')
            return False
        else:
            return True

    def _check_type_paths(self, prob):
        if type(prob[0]) is str:
            if sum([x == prob[0] for x in prob]) != len(prob):
                raise ValueError('ERROR: Not all path are defined as same type ', prob)
        elif type(prob[0]) is float:
            if sum([isinstance(x, float) for x in prob]) != len(prob):
                raise ValueError('ERROR: Not all path are defined as same type (float number) ', prob)
        else:
            raise ValueError("ERROR: Invalid input, specify the probability as AUTO, float number or CUSTOM ", prob)

    def _retrieve_check_paths(self, all_enabled_transition):
        prob = []
        for transition in all_enabled_transition:
            try:
                if transition.label:
                    prob.append(self._object_params["probability"][transition.label])
                else:
                    prob.append(self._object_params["probability"][transition.name])
            except:
                print('ERROR: Not all path probabilities are defined. Define all paths: ', all_enabled_transition)

        return prob

    def define_xor_next_activity(self, all_enabled_transition):
        """ Three different methods to decide which path following from XOR gateway:
        * Random choice: each path has equal probability to be chosen (AUTO)
        ```json
        "probability": {
            "A_ACCEPTED": "AUTO",
            "skip_2": "AUTO",
            "A_FINALIZED": "AUTO",
        }
        ```
        * Defined probability: in the file json it is possible to define for each path a specific probability (PROBABILITY as value)
        ```json
        "probability": {
            "A_PREACCEPTED": 0.20,
            "skip_1": 0.80
        }
        ```
        * Custom method: it is possible to define a dedicate method that given the possible paths it returns the one to
        follow, using whatever techniques the user prefers. (CUSTOM)
        ```json
        "probability": {
            "A_CANCELLED": "CUSTOM",
            "A_DECLINED": "CUSTOM",
            "tauSplit_5": "CUSTOM"
        }
        ```
        """
        prob = ['AUTO'] if not self._object_params["probability"] else self._retrieve_check_paths(all_enabled_transition)
        self._check_type_paths(prob)
        if prob[0] == 'AUTO':
            next = random.choices(list(range(0, len(all_enabled_transition), 1)))[0]
        elif prob[0] == 'CUSTOM':
            next = self.call_custom_xor_function(all_enabled_transition)
        elif type(prob[0] == float()):
        #elif isinstance(prob[0], float):
            if self._check_probability(prob):
                value = [*range(0, len(prob), 1)]
                next = int(random.choices(value, prob)[0])
            else:
                next = random.choices(list(range(0, len(all_enabled_transition), 1)))[0]

        return all_enabled_transition[next]

    def define_processing_time(self, activity):
        """ Three different methods are available to define the processing time for each activity:
            * Distribution function: specify in the json file the distribution with the right parameters for each
            activity, see the [numpy_distribution](https://numpy.org/doc/stable/reference/random/generator.html) distribution, (DISTRIBUTION).
            **Be careful**: A negative value generated by the distribution is not valid for the simulator.
            ```json
             "processing_time": {
                 "Add Item": { "name": "uniform", "parameters": { "low": 3600, "high": 7200}},
             }
            ```
            * Custom method: it is possible to define a dedicated method that, given the activity and its
            characteristics, returns the duration of processing time required. (CUSTOM)
            ```json
            "processing_time": {
                 "Add Item":  { "name": "custom"}
            }
            ```
            * Mixed: It is possible to define a distribution function for some activities and a dedicated method for the others.
            ```json
            "processing_time": {
                 "Add Item":  { "name": "custom"},
                 "Close Order":  { "name": "uniform", "parameters": { "low": 3600, "high": 7200}}
            }
            ```
        """
        try:
            if self._object_params["processing_time"][activity]["name"] == 'custom':
                duration = self.call_custom_processing_time()
            else:
                distribution = self._object_params["processing_time"][activity]['name']
                parameters = self._object_params["processing_time"][activity]['parameters']
                duration = getattr(np.random, distribution)(**parameters, size=1)[0]
                if duration < 0:
                    print(f"WARNING: Negative processing time {duration} of activity {activity}")
                    duration = 0
        except:
            raise ValueError("ERROR: The processing time of", activity, "is not defined in json file")
        return duration

    def define_waiting_time(self, next_act):
        """ Three different methods are available to define the waiting time before each activity:
            * Distribution function: specify in the json file the distribution with the right parameters for each
            activity, see the [numpy_distribution](https://numpy.org/doc/stable/reference/random/generator.html) distribution, (DISTRIBUTION).
            **Be careful**: A negative value generated by the distribution is not valid for the simulator.
            ```json
             "waiting_time": {
                 "Place Order":  { "name": "uniform", "parameters": { "low": 3600, "high": 7200}}
             }
            ```
            * Custom method: it is possible to define a dedicated method that, given the next activity with its
            features, returns the duration of waiting time. (CUSTOM)
            ```json
            "waiting_time": {
                 "Place Order": { "name": "custom"}
            }
            ```
            * Mixed: As the processing time, it is possible to define a mix of methods for each activity.
            ```json
            "waiting_time": {
                 "Place Order":  { "name": "custom"},
                 "Packing":  { "name": "uniform", "parameters": { "low": 3600, "high": 7200}}
            }
            ```
        """
        try:
            if self._object_params["waiting_time"][next_act]["name"] == 'custom':
                duration = self.call_custom_waiting_time()
            else:
                distribution = self._object_params["waiting_time"][next_act]['name']
                parameters = self._object_params["waiting_time"][next_act]['parameters']
                duration = getattr(np.random, distribution)(**parameters, size=1)[0]
                if duration < 0:
                    print("WARNING: Negative waiting time", duration)
                    duration = 0
        except:
            duration = 0

        return duration

    def next_transition(self, env):
        """
        Method for defining the next activity in the object's Petri net
        """
        all_enabled_transition = semantics.enabled_transitions(self._net, self._am)
        all_enabled_transition = list(all_enabled_transition)
        all_enabled_transition.sort(key=lambda x: x.name)
        if len(all_enabled_transition) == 0:
            return None
        elif len(all_enabled_transition) == 1:
            return all_enabled_transition[0]
        else:
            if len(self._am) == 1:
                return self.define_xor_next_activity(all_enabled_transition)
            else:
                events = []
                for token in self._am:
                    name = token.name
                    new_am = copy.copy(self._am)
                    tokens_to_delete = self._delete_tokens(name)
                    for p in tokens_to_delete:
                        del new_am[p]
                    path = env.process(
                        Object(self._id, self._net, new_am, self._general_params, self._process, self.prefix, "parallel",
                             self._writer, self._name_object, self._parallel_object, values_buffer=self._buffer._get_dictionary()).simulation(0, env))
                    events.append(path)
                return events
                
    def call_custom_processing_time(self):
        """
        Call to the custom functions in the file *custom_function.py*.
        """
        return self._custom.custom_processing_time(self._buffer)

    def call_custom_waiting_time(self):
        """
            Call to the custom functions in the file *custom_function.py*.
        """
        return self._custom.custom_waiting_time(self._buffer)

    def call_custom_xor_function(self, all_enabled_transition):
        """
            Call to the custom functions in the file *custom_function.py*.
        """
        objects_related_keys = self._process.get_relationships(self._id)
        object_class_list = []
        for key in objects_related_keys:
            object_class_list.append(self._process._get_specific_object(key.split("_")[0], key))
        return self._custom.custom_decision_mining(self._buffer, object_class_list, all_enabled_transition)