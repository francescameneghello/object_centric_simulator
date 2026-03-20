"""
    Class for reading simulation parameters
"""
import json
import math
import os
from datetime import datetime


class Parameters(object):

    def __init__(self, path_parameters: str):
        """TRACES: number of traces to generate"""
        self.PATH_PARAMETERS = path_parameters
        self.objects = {}
        self.process_roles = {}
        self.all_activities = []
        self.channels = {}
        """PATH_PARAMETERS: path of json file for others parameters. """
        self.read_metadata_file()

    def read_metadata_file(self):
        '''
        Method to read parameters from json file, see *main page* to get the whole list of simulation parameters.
        '''
        if os.path.exists(self.PATH_PARAMETERS):
            with open(self.PATH_PARAMETERS) as file:
                data = json.load(file)
                self.START_SIMULATION = self._check_default_parameters(data, 'start_simulation')
                for ob in data["objects"]:
                    self.objects[ob] = data["objects"][ob]
                    self._define_roles_resources(data["objects"][ob]['resource'])
                    self.all_activities += list(data["objects"][ob]["resource_table"].keys())
                    for act in data["objects"][ob]["object_constraints"]:
                        activities = data["objects"][ob]["object_constraints"][act][1]
                        for a in activities:
                            self.channels[a] = ob
        else:
            raise ValueError('Parameter file does not exist')

    def _define_roles_resources(self, roles):
        for idx, key in enumerate(roles):
            self.process_roles[key] = [roles[key]['resources'], {'days': roles[key]['calendar']['days'],
                                                                      'hour_min': roles[key]['calendar']['hour_min'],
                                                                      'hour_max': roles[key]['calendar']['hour_max']}]

    def _check_default_parameters(self, data, type):
        if type == 'start_simulation':
            value = datetime.strptime(data['start_simulation'], '%Y-%m-%d %H:%M:%S') if type in data else datetime.now()
        elif type == 'duration_simulation':
            value = data['duration_simulation']*86400 if type in data else 31536000
        return value