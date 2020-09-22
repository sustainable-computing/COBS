from model import Model

Model.set_energyplus_folder("/usr/local/EnergyPlus-9-3-0/")


class Agent:
    def __init__(self):
        pass

    def step(self, state, actions, timestep):
        print(state)


model = Model(idf_file_name="./5ZoneAirCooled.idf",
              weather_file="./USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
              agent=Agent())
# model.simulate()

state = model.reset()
while not model.is_terminate():
    print(state)
    state = model.step(list())
print("Done!!!!!!!")