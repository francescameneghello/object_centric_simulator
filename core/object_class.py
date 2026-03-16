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
import asyncio
from reactivex import operators as ops
#import custom_function as custom


CON_ACT = {'Pick Item': 'order', 'Payment Complete':'item', 'Ship':'item', 'Packing': 'truck', 'Remove Item':'order'}


class Object(object):

    def __init__(self, id: str, net: pm4py.objects.petri_net.obj.PetriNet, am: pm4py.objects.petri_net.obj.Marking,
                 params: Parameters, process: SimulationProcess, prefix: Prefix, type: str, writer: csv.writer,
                 name_object: str, father=None):
        self._id = id
        self._process = process
        self._start_time = params.START_SIMULATION
        self._general_params = params
        self._net = net
        self._am = am
        self.prefix = prefix
        self._type = type
        self._name_object = name_object
        self._object_params = params.objects[name_object]
        #if type == 'sequential':
        #    self.see_activity = False
        #else:
        #    self.see_activity = True
        self._writer = writer
        self._buffer = Buffer(writer, [])
        self._id_object = 0
        self._father = father
        self._last_activity = None
        #print(self._name_object, self._object_params)
        #self._buffer.set_feature("attribute_case", custom.case_function_attribute(self._id, time))

    def _delete_places(self, places):
        delete = []
        for place in places:
            for p in self._net.places:
                if str(place) in str(p.name):
                    delete.append(p)
        return delete

    def sample_distribution(self, distribution, parameters):
        n_sample = getattr(np.random, distribution)(**parameters, size=1)[0]
        if n_sample < 0:
            print("WARNING: Negative value", n_sample)
            n_sample = 0
        return int(n_sample)

    def check_generator(self, env, next_act):
        if next_act in self._object_params["task_generator"]:
            # "Place Order": {"obj": "item", "name": "uniform", "parameters": {"low": 2, "high": 3} },
            name_obj = self._object_params["task_generator"][next_act]["obj"]
            n_obj = self.sample_distribution(self._object_params["task_generator"][next_act]["name"], self._object_params["task_generator"][next_act]["parameters"])
            for i in range(0, n_obj):
                net, im, fm = pm4py.read_pnml(self._general_params.objects[name_obj]["path_petrinet"])
                id = f"{name_obj}_{int(self._id.rsplit('_', 1)[1])}_{self._id_object}"
                obj_class = Object(id, net, im, self._general_params, self._process, Prefix(),
                               'sequential', self._writer, name_obj, self)
                self._process.add_object(obj_class, name_obj, id)
                self._process.set_relation_ships(self._id, id)
                env.process(obj_class.simulation(env))
                self._id_object += 1

    def check_constraints(self, next_act, env):
        if next_act == 'Load':
            print(f"***************{env.now} {self._id} received new message: {self._process.board.messages}***************")
            print(env.now, self._process.relation_ships)
        info = self._object_params["object_constraints"][next_act]
        id_target_object = {x for x in self._process.get_relation_ships(self._id) if x.split('_')[0] == info[0]}
        if id_target_object:
            mesg_list = [
                msg for msg in self._process.board.messages
                if msg[1] in info[1]
            ]
            picked_items = {msg[0] for msg in mesg_list}
            matched = id_target_object & picked_items

            if info[2] == "All":
                proceed = matched == id_target_object
            elif info[2] == "Any":
                proceed = len(matched) >= 1
            else:
                proceed = len(matched) == int(info[2])

            if proceed:
                mesg_to_remove = [m for m in mesg_list if m[0] in matched]
                self._process.board.remove_message(mesg_to_remove)
                return True, matched

            return False, []
        else:
            type_objects = self._process.get_specific_type(info[0])
            mesg_list = [
                msg for msg in self._process.board.messages
                if msg[1] in info[1] and (not msg[2] or self._id in msg[2])
            ]
            picked_items = {msg[0] for msg in mesg_list}
            matched = set(type_objects.keys()) & picked_items
            if info[2] == "All":
                proceed = matched == set(type_objects.keys())
            elif info[2] == "Any":
                proceed = len(matched) >= 1
            else:
                proceed = len(matched) == int(info[2])

            if proceed:
                mesg_to_remove = [m for m in mesg_list if m[0] in matched]
                self._process.board.remove_message(mesg_to_remove)
                return True, matched
            return False, []

    def simulation(self, env: simpy.Environment):
        """
            The main function to handle the simulation of a single trace
        """
        transition = self.next_transitionition(env)
        ### register trace in process ###
        request_resource = None
        resource_trace = self._process._get_resource_trace()
        resource_trace_request = resource_trace.request() #if self._type == 'sequential' else None

        while transition is not None:
            #if not self.see_activity and self._type == 'sequential':
            yield resource_trace_request
            if transition and transition.label:  ### next transitionition to execute
                matched = []
                if transition.label in self._object_params["object_constraints"]:
                    proceed = False
                    while not proceed:
                        proceed, matched = self.check_constraints(transition.label, env)
                        if not proceed:
                            yield self._process.board.new_message_event
                    if transition.label in self._object_params["create_relation_ship"]:
                        for obj in matched:
                            self._process.set_relation_ships(self._id, obj)

                self._buffer.reset()
                self._buffer.set_feature("id_case", self._id)
                self._buffer.set_feature("activity", transition.label)
                self._buffer.set_feature("prefix",
                                         self.prefix.get_prefix(self._start_time + timedelta(seconds=env.now)))
                self._buffer.set_feature("attribute_event", {})

                ### call predictor for waiting time
                if transition.label in self._object_params["resource_table"]:
                    resource = self._process._get_resource(self._object_params["resource_table"][transition.label])
                else:
                    raise ValueError('Not resource/role defined for this activity', transition.label)

                # self._buffer.set_feature("wip_wait", 0 if type != 'sequential' else resource_trace.count-1)
                self._buffer.set_feature("wip_wait", resource_trace.count)
                self._buffer.set_feature("ro_single", self._process.get_occupations_single_role(resource._get_name()))
                self._buffer.set_feature("ro_total", self._process.get_occupations_all_role())
                self._buffer.set_feature("role", resource._get_name())

                ### register event in process ###
                resource_task = self._process._get_resource_event(transition.label)
                self._buffer.set_feature("wip_activity", resource_task.count)

                queue = 0 if len(resource._queue) == 0 else len(resource._queue[-1])
                self._buffer.set_feature("queue", queue)
                self._buffer.set_feature("enabled_time", (self._start_time + timedelta(seconds=env.now)).replace(microsecond=0))

                waiting = 0 #self.define_waiting_time(transition.label)
                #if self.see_activity:
                #    yield env.timeout(waiting)

                request_resource = resource.request()
                yield request_resource
                single_resource = self._process._set_single_resource(resource._get_name())
                self._buffer.set_feature("resource", single_resource)

                resource_task_request = resource_task.request()
                yield resource_task_request

                ### call predictor for processing time
                self._buffer.set_feature("wip_start", resource_trace.count)
                self._buffer.set_feature("ro_single", self._process.get_occupations_single_role(resource._get_name()))
                self._buffer.set_feature("ro_total", self._process.get_occupations_all_role())
                self._buffer.set_feature("wip_activity", resource_task.count)

                stop = resource.to_time_schedule(self._start_time + timedelta(seconds=env.now))
                yield env.timeout(stop)
                self._buffer.set_feature("start_time", (self._start_time + timedelta(seconds=env.now)).replace(microsecond=0))
                duration = self.define_processing_time(transition.label)
                yield env.timeout(duration)

                self._buffer.set_feature("wip_end", resource_trace.count)
                self._buffer.set_feature("end_time", (self._start_time + timedelta(seconds=env.now)).replace(microsecond=0))
                self.prefix.add_activity(transition.label)
                self.check_generator(env, transition.label)
                self._last_activity = transition.label

                if transition.label in CON_ACT:
                    rel = self._process.get_relation_ships(self._id).copy()
                    if self._father:
                        rel -= {self._father._id}
                    if transition.label in self._object_params["destroy_relation_ship"]:
                        ### SEND MESSAGE FOR EACH rel object cancelled!
                        rel = list(self._process.get_relation_ships(self._id))
                        for m in rel: ### da sistemare, cancellare solo item e non tutte relazioni
                            self._process.remove_relation_ships(self._id, m)
                    self._process.board.add_message((self._id, transition.label, rel))

                self._buffer.set_feature("relation_ships", matched)#self._define_relation_ship())
                self._buffer.print_values()
                resource.release(request_resource)
                self._process._release_single_resource(resource._get_name(), single_resource)
                resource_task.release(resource_task_request)

            self._update_marking(transition)
            transition = self.next_transitionition(env) if self._am else None

        #if self._type == 'parallel':
        #    self._parallel_object._set_last_events(self._am)
        #if self._type == 'sequential':
        self._process.remove_element(self._id)
        self._process.delete_specific_object(self._name_object, self._id)
        resource_trace.release(resource_trace_request)

    def _define_relation_ship(self):
        relation_ship = self._process.get_relation_ships(self._id)
        if self._father:
            relation_ship.add(self._father._id)
        return relation_ship

    def _get_resource_role(self, activity):
        elements = self._params.ROLE_ACTIVITY[activity.label]
        resource_object = []
        for e in elements:
            resource_object.append(self._process._get_resource(e))
        return resource_object

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
                 "A_FINALIZED": { "name": "uniform", "parameters": { "low": 3600, "high": 7200}},
             }
            ```
            * Custom method: it is possible to define a dedicated method that, given the activity and its
            characteristics, returns the duration of processing time required. (CUSTOM)
            ```json
            "processing_time": {
                 "A_FINALIZED":  { "name": "custom"}
            }
            ```
            * Mixed: It is possible to define a distribution function for some activities and a dedicated method for the others.
            ```json
            "processing_time": {
                 "A_FINALIZED":  { "name": "custom"},
                 "A_REGISTERED":  { "name": "uniform", "parameters": { "low": 3600, "high": 7200}}
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
                    print("WARNING: Negative processing time", duration)
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
                 "A_PARTLYSUBMITTED":  { "name": "uniform", "parameters": { "low": 3600, "high": 7200}}
             }
            ```
            * Custom method: it is possible to define a dedicated method that, given the next activity with its
            features, returns the duration of waiting time. (CUSTOM)
            ```json
            "waiting_time": {
                 "A_PARTLYSUBMITTED": { "name": "custom"}
            }
            ```
            * Mixed: As the processing time, it is possible to define a mix of methods for each activity.
            ```json
            "waiting_time": {
                 "A_PARTLYSUBMITTED":  { "name": "custom"},
                 "A_APPROVED":  { "name": "uniform", "parameters": { "low": 3600, "high": 7200}}
            }
            ```
        """
        try:
            if self._params.WAITING_TIME[next_act]["name"] == 'custom':
                duration = self.call_custom_waiting_time()
            else:
                distribution = self._params.WAITING_TIME[next_act]['name']
                parameters = self._params.WAITING_TIME[next_act]['parameters']
                duration = getattr(np.random, distribution)(**parameters, size=1)[0]
                if duration < 0:
                    print("WARNING: Negative waiting time", duration)
                    duration = 0
        except:
            duration = 0

        return duration

    def next_transitionition(self, env):
        """
        Method to define the next activity in the petrinet.
        """
        all_enabled_transition = semantics.enabled_transitions(self._net, self._am)
        all_enabled_transition = list(all_enabled_transition)
        all_enabled_transition.sort(key=lambda x: x.name)
        if len(all_enabled_transition) == 0:
            return None
        elif len(all_enabled_transition) == 1:
            return all_enabled_transition[0]
        else:
            return self.define_xor_next_activity(all_enabled_transition)

    '''
    parallel next transitionition:
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
                        Token(self._id, self._net, new_am, self._params, self._process, self.prefix, "parallel",
                              self._writer, self._parallel_object, self._buffer._get_dictionary()).simulation(env))
                    events.append(path)
                return events
                
    def call_custom_processing_time(self):
        """
        Call to the custom functions in the file *custom_function.py*.
        """
        return custom.custom_processing_time(self._buffer)

    def call_custom_waiting_time(self):
        """
            Call to the custom functions in the file *custom_function.py*.
        """
        return custom.custom_waiting_time(self._buffer)

    def call_custom_xor_function(self, all_enabled_transition):
        """
            Call to the custom functions in the file *custom_function.py*.
        """
        return custom.custom_decision_mining(self._buffer)
    '''