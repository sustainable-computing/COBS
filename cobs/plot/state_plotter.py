import matplotlib.pyplot as plt


def plot_state_history(model, variable, zone=None):
    temp = model.historical_values[-1]
    if isinstance(temp[variable], dict):
        if zone is None:
            for name in temp[variable]:
                data = [timestep[variable][name] for timestep in model.historical_values]
                plt.plot(data, label=name)
        else:
            data = [timestep[variable][zone] for timestep in model.historical_values]
            plt.plot(data, label=zone)
    else:
        data = [timestep[variable] for timestep in model.historical_values]
        plt.plot(data)
    plt.legend()
