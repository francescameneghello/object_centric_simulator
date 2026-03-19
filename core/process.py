import simpy
from role_simulator import RoleSimulator
import math
from parameters import Parameters
from simpy import Event


class MessageBoard:
    def __init__(self, env):
        self.env = env
        self.messages = []          # Stores all messages
        self.new_message_event = simpy.Event(env)  # Event for notifying listeners

    def add_message(self, msg):
        msg_id = msg[0]
        self.messages.append(msg)
        if not self.new_message_event.triggered:
            self.new_message_event.succeed(value=msg)
        self.new_message_event = simpy.Event(self.env)

    def remove_message(self, msg_list):
        for msg in msg_list:
            if msg in self.messages:
                self.messages.remove(msg)


class SimulationProcess(object):

    def __init__(self, env: simpy.Environment, params: Parameters):
        self._env = env
        self._params = params
        self._date_start = params.START_SIMULATION
        self._resources = self.define_single_role()
        self._resource_events = self._define_resource_events(env)
        self._resource_trace = simpy.Resource(env, math.inf)
        self._am_parallel = []
        self.board = MessageBoard(env)
        self.relation_ships = {}
        self.existing_objects = {}

    def set_relation_ships(self, id_obj_1, id_obj_2):
        if id_obj_1 in self.relation_ships:
            self.relation_ships[id_obj_1].add(id_obj_2)
        else:
            self.relation_ships[id_obj_1] = {id_obj_2}
        if id_obj_2 in self.relation_ships:
            self.relation_ships[id_obj_2].add(id_obj_1)
        else:
            self.relation_ships[id_obj_2] = {id_obj_1}

    def remove_element(self, id_obj):
        del self.relation_ships[id_obj]
        for o in self.relation_ships:
            self.relation_ships[o].discard(id_obj)

    def remove_relation_ships(self, id_obj_1, id_obj_2):
        if id_obj_1 in self.relation_ships:
            self.relation_ships[id_obj_1].discard(id_obj_2)
        if id_obj_2 in self.relation_ships:
            self.relation_ships[id_obj_2].discard(id_obj_1)

    def get_relation_ships(self, id_obj):
        return self.relation_ships[id_obj] if id_obj in self.relation_ships else {}

    def print_relation_ships(self):
        print(self.relation_ships)

    def add_object(self, object, object_type, id_object):
        self.existing_objects.setdefault(object_type, {})[id_object] = object

    def get_specific_type(self, object_type):
        return self.existing_objects[object_type] if object_type in self.existing_objects else {}

    def get_specific_object(self, object_type, id):
        return self.existing_objects[object_type][id]

    def delete_specific_object(self, object_type, id):
        del self.existing_objects[object_type][id]

    def define_single_role(self):
        """
        Definition of a *RoleSimulator* object for each role in the process.
        """
        set_resource = list(self._params.process_roles.keys())
        dict_role = dict()
        for res in set_resource:
            res_simpy = RoleSimulator(self._env, res, self._params.process_roles[res][0],
                                      self._params.process_roles[res][1])
            dict_role[res] = res_simpy
        return dict_role

    def get_occupations_single_role(self, resource):
        """
        Method to retrieve the specified role occupancy in percentage, as an intercase feature:
        $\\frac{resources \: occupated \: in \:role}{total\:resources\:in\:role}$.
        """
        occup = self._resources[resource]._get_resource().count / self._resources[resource]._capacity
        return round(occup, 2)

    def get_occupations_all_role(self):
        """
        Method to retrieve the occupancy in percentage of all roles, as an intercase feature.
        """
        list_occupations = []
        for res in self._resources:
            if res != 'TRIGGER_TIMER':
                occup = round(self._resources[res]._get_resource().count / self._resources[res]._capacity, 2)
                list_occupations.append(occup)
        return list_occupations

    def _get_resource(self, resource_label):
        return self._resources[resource_label]

    def _get_resource_event(self, task):
        return self._resource_events[task]

    def _get_resource_trace(self):
        return self._resource_trace

    def _define_resource_events(self, env):
        resources = dict()
        for key in self._params.all_activities:
            resources[key] = simpy.Resource(env, math.inf)
        return resources

    def _set_single_resource(self, resource_task):
        return self._resources[resource_task]._get_resources_name()

    def _release_single_resource(self, role, resource):
        self._resources[role]._release_resource_name(resource)