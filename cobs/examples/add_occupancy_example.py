"""
This is an example of how to add the occupancy into the model.
"""

from cobs import Model

Model.set_energyplus_folder("D:\\Software\\EnergyPlus\\")

mode = 1

model = Model(idf_file_name="../data/buildings/5ZoneAirCooled.idf",
              weather_file="../data/weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",)

# Example of how to check the required fields for a new component
print(model.get_sub_configuration("Output:Variable"))

# --------------------------------------------------------------------------
#                Sample of adding occupancy movement manually
# --------------------------------------------------------------------------
if mode == 1:
    # Setup values for new components
    occu_schedule_values = {"Name": "Test_Schedule",
                            "Schedule Type Limits Name": "Fraction",
                            "Field 1": "Through: 12/31",
                            "Field 2": "For: Alldays",
                            "Field 3": "Until: 05:00",
                            "Field 4": "0",
                            "Field 5": "Until 09:00",
                            "Field 6": "0.5",
                            "Field 7": "Until 17:00",
                            "Field 8": "0.95",
                            "Field 9": "Until 24:00",
                            "Field 10": "0.5"}

    activity_values = {"Name": "Test_Activity_Schedule",
                       "Schedule Type Limits Name": "Any Number",
                       "Field 1": "Through:12/31",
                       "Field 2": "For: Alldays",
                       "Field 3": "Until 24:00",
                       "Field 4": "117"}

    work_efficiency = {"Name": "Test_Work_Schedule",
                       "Schedule Type Limits Name": "Fraction",
                       "Field 1": "Through:12/31",
                       "Field 2": "For: Alldays",
                       "Field 3": "Until 24:00",
                       "Field 4": "0.1"}

    cloth_schedule = {"Name": "Test_Cloth_Schedule",
                      "Schedule Type Limits Name": "Fraction",
                      "Field 1": "Through:12/31",
                      "Field 2": "For: Alldays",
                      "Field 3": "Until 24:00",
                      "Field 4": "0.9"}

    air_velocity = {"Name": "Test_Air_Velocity",
                    "Schedule Type Limits Name": "Fraction",
                    "Field 1": "Through:12/31",
                    "Field 2": "For: Alldays",
                    "Field 3": "Until 24:00",
                    "Field 4": "0.25"}

    people_values = {"Name": "Test",
                     "Zone or ZoneList Name": "SPACE1-1",
                     "Number of People Schedule Name": "Test_Schedule",
                     "Number of People": 5,
                     "Activity Level Schedule Name": "Test_Activity_Schedule",
                     "Work Efficiency Schedule Name": "Test_Work_Schedule",
                     "Clothing Insulation Schedule Name": "Test_Cloth_Schedule",
                     "Air Velocity Schedule Name": "Test_Air_Velocity",
                     "Thermal Comfort Model 1 Type": "Fanger"}
    print(model.add_configuration("Schedule:Compact", values=occu_schedule_values))
    print(model.add_configuration("Schedule:Compact", values=activity_values))
    print(model.add_configuration("Schedule:Compact", values=work_efficiency))
    print(model.add_configuration("Schedule:Compact", values=cloth_schedule))
    print(model.add_configuration("Schedule:Compact", values=air_velocity))
    print(model.add_configuration("People", values=people_values))
    print(model.add_configuration("Output:Variable", values={"Variable Name": "Zone Thermal Comfort Fanger Model PMV",
                                                             "Reporting_Frequency": "timestep"}))

# --------------------------------------------------------------------------
#            Sample of adding occupancy using OccupancyGenerator
# --------------------------------------------------------------------------
elif mode == 2:
    from cobs import OccupancyGenerator as OG

    OG(model).generate_daily_schedule(add_to_model=True,
                                      overwrite_dict={f"SPACE{i}-1": f"SPACE{i}-1 People 1"
                                                      for i in range(1, 6)}
                                      )

# Example of check what is available for the state value
print(model.get_current_state_values())

if __name__ == '__main__':
    state = model.reset()
    while not model.is_terminate():
        print(state)
        state = model.step(list())
    print("Done")
