import json
from random import choices, seed


# Assume a interior blind
class BlindController:
    def __init__(self, model, priority=0, config_location=None, seed_num=None):
        self.model = model
        self.priority = priority
        self.blind_config = config_location
        if config_location is not None:
            with open(config_location, 'r') as infile:
                self.blind_config = json.load(infile)
        self.mapping = {"on": 1, "off": 0}
        self.seed_num = seed_num

    def generate_template(self, output_name=None):
        if output_name is None:
            output_name = "blind_config.json"

        zone_blinds = self.model.get_windows()
        self.blind_config = dict()
        for zone in zone_blinds:
            self.blind_config[zone] = dict()
            for blind in zone_blinds[zone]:
                self.blind_config[zone][blind] = {"on": {"occupancy > 0 and occupancy < 2": 0.8,
                                                         "occupancy > 2": 1,
                                                         "temperature > 30": 0},
                                                  "off": {"abs(PMV) > 1": 1}}

        with open(output_name, 'w') as outfile:
            json.dump(self.blind_config, outfile)

    def update(self, state, environment):

        if self.blind_config is None:
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

            for blind in self.blind_config[zone]:
                action_prob = {"on": 0, "off": 0}

                for action in self.blind_config[zone][blind]:
                    conditions = self.blind_config[zone][blind][action]
                    for condition, prob in conditions.items():
                        try:
                            if eval(condition) and action_prob[action] < prob:
                                action_prob[action] = prob
                        except NameError:
                            pass

                actions = list(action_prob.keys())
                probs = [action_prob[a] for a in actions]

                action = choices(actions, probs)
                # print(f"blind: {blind}, action: {action}")
                self.model.queue.schedule_event(value=action,
                                                start_time=state["timestep"] + 1,
                                                priority=self.priority,
                                                component_type="Window Shading Control",
                                                control_type="Control Status",
                                                actuator_key=f"{blind}")
