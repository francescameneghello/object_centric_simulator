"""
* Prefix: Class to track the sequence of activities observed for an object
* Buffer: Class to store all the fields of one event.
"""

import os


def define_folder_output(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


class ParallelObject(object):

    def __init__(self):
        self._am_parallel = []

    def _set_last_events(self, am):
        for token in am:
            self._am_parallel.append(token)

    def _get_last_events(self):
        tokens = set(self._am_parallel)
        self._am_parallel = []
        return tokens

    def _update_last_events(self):
        self._am_parallel = []


class Prefix(object):

    def __init__(self):
        self._list_activities = list()

    def add_activity(self, activity):
        self._list_activities.append(activity)

    def get_prefix(self, time):
        return self._list_activities


class Buffer(object):
    def __init__(self, writer, values=None):
        self.buffer = {
            "obj_id": -1,
            "activity": None,
            "enabled_time": None,
            "start_time": None,
            "end_time": None,
            "role": None,
            "resource": None,
            "wip_wait": -1,
            "wip_start": -1,
            "wip_end": -1,
            "wip_activity": -1,
            "ro_total": [],
            "ro_single": -1,
            "queue": -1,
            "prefix": Prefix,
            "relationships": [],
            "attribute_object": dict(),
        }
        if values:
            self._decopy_value(values)
        self.writer = writer

    def _decopy_value(self, values):
        for key in values:
            self.buffer[key] = values[key]

    def _get_dictionary(self):
        return self.buffer

    def set_feature(self, feature, value):
        if isinstance(self.buffer[feature], list):
            self.buffer[feature] = value
        else:
            self.buffer[feature] = value

    def get_feature(self, feature):
        return self.buffer[feature]

    def print_values(self):
        keys_to_print = ["obj_id", "activity", "enabled_time", "start_time",
                         "end_time", "role", "resource", "prefix", "relationships", "attribute_object"]
        subset = {k: self.buffer[k] for k in keys_to_print if k in self.buffer}
        print(*subset.values())
        self.writer.writerow(self.buffer.values())

    def get_buffer_keys(self):
        return self.buffer.keys()
    
    def update_object_attribute(self, transition_label, object_attribute):
        return self.buffer
    #TODO FIX
    def reset(self):
        self.buffer["enabled_time"] = None
        self.buffer["start_time"] = None
        self.buffer["end_time"] = None
        self.buffer["resource"] = None
        self.buffer["wip_wait"] = -1
        self.buffer["wip_start"] = -1
        self.buffer["wip_end"] = -1
        self.buffer["wip_activity"] = -1
        self.buffer["ro_total"] = []
        self.buffer["ro_single"] = -1
        self.buffer["queue"] = -1
        self.buffer['relationships'] = []