"""
Class to manage the arrivals times of tokes in the process.
"""

import numpy as np
from datetime import datetime, timedelta
from importlib import import_module


class InterTriggerTimer(object):

    def __init__(self, inter_trigger_config, process, start: datetime, name_exp: None):
        self._process = process
        self._start_time = start
        self._type = inter_trigger_config['type']
        self._previous = None
        self._name_exp = name_exp
        self._custom = import_module(f"input.experiments.{self._name_exp}.custom_function")
        
        if self._type == 'distribution':
            """Define the distribution of token arrivals from specified in the file json"""
            self.name_distribution = inter_trigger_config['name']
            self.params = inter_trigger_config['parameters']

    def get_next_arrival(self, env, obj):
        """Generate a new arrival from the distribution defined in the file json or from a custom function defined in custom_function.py"""
        next = 0
        if self._type == 'distribution':
            arrival = getattr(np.random, self.name_distribution)(**self.params, size=1)[0]
            next = arrival
        elif self._type == 'custom':
            next = self.custom_arrival(obj, self._previous)
        else:
            raise ValueError('ERROR: Invalid arrival times generator')
        self._previous = self._start_time + timedelta(seconds=env.now + next)
        return next

    def custom_arrival(self, obj, previous):
        """
        Call to the custom functions in the file custom_function.py.
        """
        return self._custom.custom_arrivals_time(obj, previous)

