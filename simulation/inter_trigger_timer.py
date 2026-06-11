"""
Class to manage the arrivals times of tokes in the process.
"""

import numpy as np
from datetime import datetime, timedelta
from parameters import Parameters
from process import SimulationProcess
import custom_function as custom


class InterTriggerTimer(object):

    def __init__(self, inter_trigger_config, process, start: datetime):
        self._process = process
        self._start_time = start
        self._type = inter_trigger_config['type']
        self._previous = None
        if self._type == 'distribution':
            """Define the distribution of token arrivals from specified in the file json"""
            self.name_distribution = inter_trigger_config['name']
            self.params = inter_trigger_config['parameters']

    def get_next_arrival(self, env, case):
        """Generate a new arrival from the distribution defined in the file json or from a custom function defined in custom_function.py"""
        next = 0
        if self._type == 'distribution':
            arrival = getattr(np.random, self.name_distribution)(**self.params, size=1)[0]
            next = arrival
        elif self._type == 'custom':
            next = self.custom_arrival(case, self._previous)
        else:
            raise ValueError('ERROR: Invalid arrival times generator')
        self._previous = self._start_time + timedelta(seconds=env.now + next)
        return next

    def custom_arrival(self, case, previous):
        """
        Call to the custom functions in the file custom_function.py.
        """
        return custom.custom_arrivals_time(case, previous)

