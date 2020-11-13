"""
This is an example of how to run a simple simulation using COBS.
This dummy agent send no action to the environment and print out
the state value of the current timestep until done.
"""
import sys
sys.path.insert(0, "D:\\Work\\COBS\\")
from cobs import Model

Model.set_energyplus_folder("D:\\Software\\EnergyPlus\\")


# --------------------------------------------------------------------------
#                     Sample dummy agent 1 using a class
# --------------------------------------------------------------------------
def run_example_1():
    class Agent:
        def __init__(self):
            pass

        def step(self, state, actions, timestep):
            print(f"Timestep: {timestep}, State values: {state}")

    model = Model(idf_file_name="../data/buildings/5ZoneAirCooled.idf",
                  weather_file="../data/weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
                  agent=Agent())
    model.simulate()
    print("Done")


# --------------------------------------------------------------------------
#             Sample dummy agent 2 using a OpenAI Gym interface
# --------------------------------------------------------------------------
def run_example_2():
    model = Model(idf_file_name="../data/buildings/5ZoneAirCooled.idf",
                  weather_file="../data/weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    state = model.reset()
    while not model.is_terminate():
        print(state)
        state = model.step(None)
    print("Done")


if __name__ == '__main__':
    mode = 2
    if mode == 1:
        run_example_1()
    else:
        run_example_2()
