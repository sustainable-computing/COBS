from model import Model

Model.set_energyplus_folder("/usr/local/EnergyPlus-9-3-0/")


class Agent:
    def __init__(self):
        pass

    def step(self, state):
        print(state)


model = Model(idf_file_name="./buildings/5ZoneAirCooled.idf",
              weather_file="./weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
              agent=Agent())
model.simulate()
