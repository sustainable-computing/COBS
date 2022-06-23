class EventQueue:
    def __init__(self):
        """
        A priority queue schedule all actions.
        """
        self.queue = dict()
        self.extra_events = dict()
        self.lockdown = -1

    def add_extra_events(self,
                         value_name: str,
                         priority: int,
                         value,
                         start_time: int,
                         end_time: int = None,
                         note: str = None):
        """
        Add events/actions that is not for the EnergyPlus to run.
        This action is stored in a separate queue for other agents/predictive models/estimation models to use.

        :param value_name: Name of the action.
        :param priority: An integer. Lower value indicates a higher priority.
        :param value: Action value.
        :param start_time: When this action will be triggered.
        :param end_time: (Optional) When this action will stop.
        :param note: (Optional) Placeholder for extra information.
        :return: None.
        """
        if end_time is None:
            end_time = start_time + 1
        for time in range(start_time, end_time):
            if time < self.lockdown:
                continue
            self.extra_events[time] = self.queue.get(time, dict())
            previous = self.extra_events[time].get(value_name, None)
            if previous is None or previous[0] > priority:
                self.extra_events[time][value_name] = [priority, value, note]

    def schedule_event(self,
                       value,
                       start_time: int,
                       priority: int,
                       type: str = "actuator",
                       dict_target: dict = None,
                       component_type: str = None,
                       control_type: str = None,
                       actuator_key: str = None,
                       var_name: str = None,
                       end_time: int = None,
                       note: str = None):
        """
        Add events/actions that is for the EnergyPlus to run.

        :param value: Action value.
        :param start_time: When this action will be triggered.
        :param priority: An integer. Lower value indicates a higher priority.
        :param type: One of ``actuator`` and ``global``.
        :param dict_target: A dictionary type of action contains the ``component_type``, ``control_type``, and ``actuator_key``.
        :param component_type: A string same as the EnergyPlus component type.
        :param control_type: A string same as the EnergyPlus control type.
        :param actuator_key: A string same as the EnergyPlus actuator name.
        :param var_name: A string same as the EnergyPlus global controller name.
        :param end_time: (Optional) When this action will stop.
        :param note: (Optional) Placeholder for extra information.
        :return: None.
        """

        control_str = ""
        if type == "actuator":
            if dict_target is not None:
                control_str = "|*|".join([dict_target["Component Type"],
                                          dict_target["Control Type"],
                                          dict_target["Actuator Key"]])
            else:
                control_str = "|*|".join([component_type, control_type, actuator_key])
        elif type == "global":
            control_str = var_name
        else:
            raise ValueError("Invalud control input")

        if end_time is None:
            end_time = start_time + 1
        for time in range(start_time, end_time):
            if time < self.lockdown:
                continue
            self.queue[time] = self.queue.get(time, {"actuator": dict(), "global": dict()})
            previous = self.queue[time][type].get(control_str, None)
            if previous is None or previous[0] > priority:
                self.queue[time][type][control_str] = [priority, value, note]

    def get_event(self,
                  time: int):
        """
        Get all events/actions that happens at a given time.

        :param time: Target time.
        :return: a dictionary contains all events/actions scheduled at the given time.
        """
        return self.queue.pop(time, {"actuator": dict(), "global": dict()})

    def trigger(self,
                current_time: int):
        """
        Get all events/actions that happens at a given time.
        In the meantime, lock all happened actions. No more actions can be scheduled before the given time.

        :param current_time: Target time.
        :return: a dictionary contains all events/actions scheduled at the given time.
        """
        self.lockdown = current_time
        return self.get_event(current_time)
