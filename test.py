import cobs
import numpy as np

cobs.Model.set_energyplus_folder("/usr/local/EnergyPlus-9-3-0/")

if __name__ == '__main__':
    model = cobs.Model(idf_file_name="./cobs/data/buildings/5ZoneAirCooled.idf",
                       weather_file="./cobs/data/weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    og = cobs.OccupancyGenerator(model)
    occupancy = np.ones((365, 3, 24 * 60))
    og.generate_schedule_using_numpy(occupancy)
    # model.
    # print(model.add_configuration("Schedule:Day:Interval"))
    occupancy[1, 0, 0:8 * 60] = 0
    print(og.one_day_numpy_to_schedule(occupancy[1, 0, :], name="TESTING"))

    exit(0)
    state = model.reset()
    while not model.is_terminate():
        print(state)
        state = model.step()

    print(state)
    print("Done")
