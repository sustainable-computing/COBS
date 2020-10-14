import json
from random import choices, seed


class LightController:
    def __init__(self, model, priority=0, config_location=None, seed_num=None):
        self.model = model
        self.priority = priority
        self.light_config = config_location
        if config_location is not None:
            with open(config_location, 'r') as infile:
                self.light_config = json.load(infile)
        self.mapping = {"on": 1, "off": 0}
        self.seed_num = seed_num

    def generate_template(self, output_name=None):
        if output_name is None:
            output_name = "light_config.json"

        zone_lights = self.model.get_lights()
        self.light_config = dict()
        for zone in zone_lights:
            self.light_config[zone] = dict()
            for light in zone_lights[zone]:
                self.light_config[zone][light] = {"on": {"occupancy > 0 and occupancy < 2": 0.8,
                                                         "occupancy > 2": 1,
                                                         "temperature > 30": 0},
                                                  "off": {"abs(PMV) > 1": 1}}

        with open(output_name, 'w') as outfile:
            json.dump(self.light_config, outfile)

    def update(self, state, environment):

        if self.light_config is None:
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

            for light in self.light_config[zone]:
                action_prob = {"on": 0, "off": 0}

                for action in self.light_config[zone][light]:
                    conditions = self.light_config[zone][light][action]
                    for condition, prob in conditions.items():
                        try:
                            if eval(condition) and action_prob[action] < prob:
                                action_prob[action] = prob
                        except NameError:
                            pass

                actions = list(action_prob.keys())
                probs = [action_prob[a] for a in actions]

                action = self.mapping[choices(actions, probs)[0]]
                # print(f"light: {light}, action: {action}")
                self.model.queue.schedule_event(value=action,
                                                start_time=state["timestep"] + 1,
                                                priority=self.priority,
                                                component_type="Lights",
                                                control_type="Electric Power Level",
                                                actuator_key=light)
