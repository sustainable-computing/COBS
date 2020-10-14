"""
This is an example of how to run a simple simulation using COBS.
This dummy agent send no action to the environment and print out
the state value of the current timestep until done.
"""

from model import Model

Model.set_energyplus_folder("/usr/local/EnergyPlus-9-3-0/")

mode = 1
# --------------------------------------------------------------------------
#                     Sample dummy agent 1 using a class
# --------------------------------------------------------------------------
if mode == 1:
    class Agent:
        def __init__(self):
            pass

        def step(self, state, actions, timestep):
            print(f"Timestep: {timestep}, State values: {state}")


    model = Model(idf_file_name="../buildings/5ZoneAirCooled.idf",
                  weather_file="../weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
                  agent=Agent())
    model.simulate()
    print("Done")


# --------------------------------------------------------------------------
#             Sample dummy agent 2 using a OpenAI Gym interface
# --------------------------------------------------------------------------
elif mode == 2:
    model = Model(idf_file_name="../buildings/5ZoneAirCooled.idf",
                  weather_file="../weathers/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
    state = model.reset()
    while not model.is_terminate():
        print(state)
        state = model.step(list())
    print("Done")
