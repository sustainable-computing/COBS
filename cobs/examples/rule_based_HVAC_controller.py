"""
This is an example of how to implement a rule-based controller. This controller set the heating setpoint to 20
and the cooling setpoint to 24 when the zone is occupied, and the heating setpoint to 18 and the cooling setpoint
to 26 when the zone is unoccupied. There is a minor bug with the EnergyPlus occupancy state, and will be fixed
in the next version.
"""

import numpy as np
from cobs import OccupancyGenerator as OG
from cobs import Model

Model.set_energyplus_folder("D:\\Software\\EnergyPlus\\")


# --------------------------------------------------------------------------
#                Sample of rule-based controller using class
# --------------------------------------------------------------------------
def run_example_1():
    class Agent:
        def __init__(self):
            self.total_reward = dict()
            self.zone_occupancy = None
            self.zone_names = None
            self.temp_set = 22
            self.delta_occ = 2
            self.delta_unocc = 4
            self.energy = list()

        def step(self, state, action_queue, timestep):
            for zone, temp in state["temperature"].items():
                state["occupancy"][zone] = self.zone_occupancy[self.zone_names.index(zone), timestep]
                if zone == "PLENUM-1":
                    continue
                if temp > 20 and temp < 24:
                    continue
                if state["occupancy"][zone] > 0:
                    delta = self.delta_occ
                else:
                    delta = self.delta_unocc
                action_queue.schedule_event(self.temp_set + delta, timestep + 1, 0,
                                            component_type="Zone Temperature Control",
                                            control_type="Cooling Setpoint",
                                            actuator_key=zone)
                action_queue.schedule_event(self.temp_set - delta, timestep + 1, 0,
                                            component_type="Zone Temperature Control",
                                            control_type="Heating Setpoint",
                                            actuator_key=zone)
            self.energy.append(state["energy"])

    agent = Agent()
    model = Model(idf_file_name="../data/buildings/5ZoneAirCooled.idf",
                  weather_file="../data/weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
                  agent=agent)

    _, locations, zone_occupancy, names = OG(model).generate_daily_schedule()
    agent.zone_occupancy = zone_occupancy
    agent.zone_names = names

    model.simulate()
    energy = np.sum(agent.energy)
    print(f"Total energy used: {energy}J ({energy / 3600000} kWh)")


# --------------------------------------------------------------------------
#         Sample of rule-based controller using OpenAI Gym interface
# --------------------------------------------------------------------------
def run_example_2():
    model = Model(idf_file_name="../data/buildings/5ZoneAirCooled.idf",
                  weather_file="../data/weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")

    _, locations, zone_occupancy, zone_names = OG(model).generate_daily_schedule()

    state = model.reset()
    energy = [state["energy"]]
    timestep = 0
    while not model.is_terminate():
        actions = list()
        for zone, temp in state["temperature"].items():
            state["occupancy"][zone] = zone_occupancy[zone_names.index(zone), timestep]
            if zone == "PLENUM-1":
                continue
            if temp > 20 and temp < 24:
                continue
            if state["occupancy"][zone] > 0:
                delta = 2
            else:
                delta = 4
            actions.append({"value": 22 + delta,
                            "start_time": timestep + 1,
                            "priority": 0,
                            "component_type": "Zone Temperature Control",
                            "control_type": "Cooling Setpoint",
                            "actuator_key": zone})
            actions.append({"value": 22 - delta,
                            "start_time": timestep + 1,
                            "priority": 0,
                            "component_type": "Zone Temperature Control",
                            "control_type": "Heating Setpoint",
                            "actuator_key": zone})
        timestep += 1
        state = model.step(actions)
        energy.append(state["energy"])

    energy = np.sum(energy)
    print(f"Total energy used: {energy}J ({energy / 3600000} kWh)")


if __name__ == '__main__':
    mode = 1
    if mode == 1:
        run_example_1()
    else:
        run_example_2()
