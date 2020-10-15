import pandas as pd
from datetime import timedelta


class CsvImporter:
    def __init__(self, file_name, planstep=12):
        data_frame = pd.read_csv(file_name, index_col=0)
        # Read forecasted variables
        forecast_vars = [
            "Outdoor Temp.",
            "Total Rad.",
            "Occupancy Flag"
        ]

        data_frame['Total Rad.'] = data_frame['Diff. Solar Rad.'] + data_frame['Direct Solar Rad.']
        data_frame.index = pd.to_datetime(data_frame.index)
        self.forecasted = data_frame[forecast_vars]
        self.forecasted = (self.forecasted - self.forecasted.min()) / (self.forecasted.max() - self.forecasted.min())
        self.planstep = planstep

    def step(self, true_state, environment):
        del environment
        time = true_state["time"]
        minute = round(time.minute / 15) % 4 * 15
        time = time.replace(year=1991, minute=minute)

        for i in range(self.planstep):
            value = self.forecasted.loc[str(time + timedelta(minutes=15 * i))]
            for name in self.forecasted.columns:
                true_state[f"{name} {i}"] = value[name]

    def get_output_states(self):
        names = list()
        for i in range(self.planstep):
            for name in self.forecasted.columns:
                names.append(f"{name} {i}")
        return names

    def ignore_by_checkpoint(self):
        return self.get_output_states()

