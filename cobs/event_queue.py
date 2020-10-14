class EventQueue:
    def __init__(self):
        """
        queue: dict
            time -> dict
                    {
                        actuator -> {component|*|ctrl|*|key -> [priority, value]}
                        global -> {var_name -> [priority, value]}
                    }
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
                       priority: int,  # lower with higher priority
                       type: str = "actuator",  # Actuator or global
                       dict_target: dict = None,
                       component_type: str = None,
                       # https://nrel.github.io/EnergyPlus/api/python/_modules/datatransfer.html#DataExchange.get_actuator_handle
                       control_type: str = None,
                       actuator_key: str = None,
                       var_name: str = None,
                       end_time: int = None,
                       note: str = None):

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
        return self.queue.get(time, {"actuator": dict(), "global": dict()})

    def trigger(self,
                current_time: int):
        self.lockdown = current_time
        return self.get_event(current_time)
