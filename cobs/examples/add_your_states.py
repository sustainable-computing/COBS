"""
This is an example of how to add your own states using COBS.
Here we demonstrate two new states: VAV position and CO2 concentration
Remember adding new state is not easy, and you have to know how to do it
in EnergyPlus IDF file.
"""
import sys

sys.path.insert(0, "D:\\Work\\COBS\\")
import cobs
import matplotlib.pyplot as plt

if __name__ == '__main__':
    cobs.Model.set_energyplus_folder("D:\\Software\\EnergyPlus\\")

    # A dictionary formatted as {target sensor: state name}
    # Target sensor is a tuple: (variable name, key value)
    eplus_extra_states = {("Zone Air Terminal VAV Damper Position", "SPACE1-1 VAV Reheat"): "Space 1-1 VAV",
                          ("Zone Air Terminal VAV Damper Position", "SPACE2-1 VAV Reheat"): "Space 2-1 VAV",
                          ("Schedule Value", "SPACE1-1 VAV Customized Schedule"): "VAV Setpoint",
                          ("Zone Air CO2 Concentration", "SPACE1-1"): "SPACE1-1 CO2",
                          ("Zone Air CO2 Concentration", "SPACE2-1"): "SPACE2-1 CO2"}

    model = cobs.Model(idf_file_name="../data/buildings/5ZoneAirCooled.idf",
                       weather_file="../data/weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
                       eplus_naming_dict=eplus_extra_states)

    # Add these sensing option into the IDF file (optional, if IDF already contains them, you can ignore it)
    for key, _ in eplus_extra_states.items():
        model.add_configuration("Output:Variable",
                                {"Key Value": key[1], "Variable Name": key[0], "Reporting Frequency": "Timestep"})

    # Because the SPACE1-1 VAV Customized Schedule does not exist (I added to control the VAV), so add to the IDF
    model.add_configuration("Schedule:Constant",
                            {"Name": "SPACE1-1 VAV Customized Schedule",
                             "Schedule Type Limits Name": "Fraction",
                             "Hourly Value": 0})

    # Overwrite existing VAV control policy to gain customized control
    model.edit_configuration(
        idf_header_name="AirTerminal:SingleDuct:VAV:Reheat",
        identifier={"Name": "SPACE1-1 VAV Reheat"},
        update_values={"Zone Minimum Air Flow Input Method": "Scheduled",
                       "Minimum Air Flow Fraction Schedule Name": "SPACE1-1 VAV Customized Schedule"})

    # Add simulation of CO2 concentration. It is not included in 5ZoneAirCooled.idf, so I add it here
    # You have to provide the outdoor CO2 concentration in order to let Energyplus calculate the indoor CO2
    # Here I use a fixed 410.25 ppm as the outdoor CO2 concentration
    model.add_configuration("Schedule:Constant",
                            {"Name": "Outdoor CO2 Schedule",
                             "Schedule Type Limits Name": "Any Number",
                             "Hourly Value": 410.25})
    model.add_configuration("ZoneAirContaminantBalance",
                            {"Carbon Dioxide Concentration": "Yes",
                             "Outdoor Carbon Dioxide Schedule Name": "Outdoor CO2 Schedule"})

    # Simulate for 20 days, 10 minute time interval
    model.set_runperiod(20)
    model.set_timestep(10)

    vav_1_pos = list()
    vav_2_pos = list()
    vav_1_stpt = 0.8  # In this example, I force the SPACE1-1 VAV to 80% open all the time

    co2_1 = list()
    co2_2 = list()

    obs = model.reset()
    while not model.is_terminate():
        vav_1_pos.append(obs["Space 1-1 VAV"])
        vav_2_pos.append(obs["Space 2-1 VAV"])
        co2_1.append(obs["SPACE1-1 CO2"])
        co2_2.append(obs["SPACE2-1 CO2"])

        actions = list()
        actions.append({"priority": 0,
                        "component_type": "Schedule:Constant",
                        "control_type": "Schedule Value",
                        "actuator_key": "SPACE1-1 VAV Customized Schedule",
                        "value": vav_1_stpt,
                        "start_time": obs['timestep'] + 1})
        obs = model.step(actions)
        print(f"Progress: {obs['timestep'] + 1}/{model.get_total_timestep()}")
    print("Done.")

    plt.plot(vav_1_pos, label="Space 1-1 VAV")
    plt.plot(vav_2_pos, label="Space 2-1 VAV")
    plt.legend()
    plt.show()

    plt.plot(co2_1, label="Space 1-1 CO2")
    plt.plot(co2_2, label="Space 2-1 CO2")
    plt.legend()
    plt.show()
