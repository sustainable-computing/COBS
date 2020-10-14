import json
from random import choices, seed


class WindowController:
    def __init__(self, model, priority=0, config_location=None, seed_num=None):
        self.model = model
        self.priority = priority
        self.window_config = config_location
        if config_location is not None:
            with open(config_location, 'r') as infile:
                self.window_config = json.load(infile)
        self.mapping = {"on": 1, "off": 0}
        self.seed_num = seed_num

        # self.model.delete_configuration("ZoneInfiltration:EffectiveLeakageArea")
        for name in self.model.get_available_names_under_group("Zone"):
            if len(self.model.get_windows()[name]) == 0:
                continue
            schedule = {"Name": f"{name}_Window",
                        "Schedule Type Limits Name": "Fraction",
                        "Field 1": "Through:12/31",
                        "Field 2": "For: Alldays",
                        "Field 3": "Until 24:00",
                        "Field 4": "0"}
            self.model.add_configuration("Schedule:Compact", values=schedule)

            leakage = {"Name": f"{name}_WindowLeakage",
                       "Zone Name": name,
                       "Schedule Name": f"{name}_Window",
                       "Effective Air Leakage Area": 500.0,
                       "Stack Coefficient": 0.000145,
                       "Wind Coefficient": 0.000174}
            self.model.add_configuration("ZoneInfiltration:EffectiveLeakageArea", values=leakage)

    def generate_template(self, output_name=None):
        if output_name is None:
            output_name = "window_config.json"

        zone_windows = self.model.get_windows()
        self.window_config = dict()
        for zone in zone_windows:
            self.window_config[zone] = dict()
            for window in zone_windows[zone]:
                self.window_config[zone][window] = {"on": {"occupancy > 0 and occupancy < 2": 0.8,
                                                           "occupancy > 2": 1,
                                                           "temperature > 30": 0},
                                                    "off": {"abs(PMV) > 1": 1}}

        with open(output_name, 'w') as outfile:
            json.dump(self.window_config, outfile)

    def update(self, state, environment):

        if self.window_config is None:
            return
        if self.seed_num:
            seed(self.seed_num)
        for zone in state["occupancy"]:
            if state["occupancy"][zone] <= 0:
                continue
            for available_variable in state:
                if isinstance(state[available_variable], dict):
                    if zone in state[available_variable]:
                        exec(f"{available_variable} = {state[available_variable][zone]}")
                else:
                    exec(f"{available_variable} = {state[available_variable]}")

            for window in self.window_config[zone]:
                action_prob = {"on": 0, "off": 0}

                for action in self.window_config[zone][window]:
                    conditions = self.window_config[zone][window][action]
                    for condition, prob in conditions.items():
                        try:
                            if eval(condition) and action_prob[action] < prob:
                                action_prob[action] = prob
                        except NameError:
                            pass

                actions = list(action_prob.keys())
                probs = [action_prob[a] for a in actions]

                action = self.mapping[choices(actions, probs)[0]]
                # print(f"window: {window}, action: {action}")
                self.model.queue.schedule_event(value=action,
                                                start_time=state["timestep"] + 1,
                                                priority=self.priority,
                                                component_type="Schedule:Compact",
                                                control_type="Schedule Value",
                                                actuator_key=f"{zone}_WINDOW")
