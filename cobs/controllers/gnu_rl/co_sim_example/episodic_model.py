import sys, pdb

import torch
import pandas as pd

# from eventqueue import EventQueue
from eppy.modeleditor import IDF
from eppy.bunch_subclass import BadEPFieldError
# from pyenergyplus.api import EnergyPlusAPI


def r_func(obs_dict, action, eta):
    # TODO - user should be able to specify reward function
    (action, SAT_stpt) = action
    r = - 0.5 * eta[int(obs_dict["Occupancy Flag"])] * (
            obs_dict["Indoor Temp."] - obs_dict["Indoor Temp. Setpoint"]) ** 2 - action

    return r


class Agent:
    def __init__(self):
        pass


class EpisodicModel:
    model_import_flag = False

    # TODO - user should define actions outside of the model

    # EnergyManagementSystem:Actuator Available,
    #   VAV SYS 1 OUTLET NODE,
    #   System Node Setpoint,
    #   Temperature Setpoint,[C]
    component_type = "System Node Setpoint"
    control_type = "Temperature Setpoint"
    actuator_key = "VAV SYS 1 OUTLET NODE"

    # EnergyManagementSystem:Actuator Available,
    #   SEASONAL RESET SUPPLY AIR TEMP SCH,
    #   Schedule:Compact,
    #   Schedule Value
    # component_type = "Schedule:Compact"
    # control_type = "Schedule Value"
    # actuator_key = "SEASONAL RESET SUPPLY AIR TEMP SCH"

    component_type = "Schedule:Constant"
    control_type = "Schedule Value"
    actuator_key = "SAT_SP"

    @classmethod
    def set_energyplus_folder(cls, path):
        sys.path.insert(0, path)
        IDF.setiddname(f"{path}Energy+.idd")
        cls.model_import_flag = True

    def __init__(self,
                 idf_file_name: str,
                 weather_file: str,
                 year: int,
                 step: int,
                 eplus_naming_dict: dict,
                 eplus_var_types: dict,
                 state_name: list = None,
                 max_episodes: int = None,
                 max_episode_steps: int = None,
                 agent: Agent = None,
                 ):
        """
        Refer to EMS application guide:
        https://bigladdersoftware.com/epx/docs/9-3/ems-application-guide/ems-calling-points.html#ems-calling-points
        for infomration on control flow

        :param idf_file_name: The path to the idf file
        :param weather_file: The path to the epw file
        :param tol_eps: An integer representing the total amount of episodes
        :param n_step: An integer representing the max number of steps per episode
        :param agent: An agent object. Used for control.
        """
        # Setup Energy Plus
        self.api = None
        self.year = year
        if not EpisodicModel.model_import_flag:
            raise ImportError("You have to set the energyplus folder first")
        self.run_parameters = ["-d", "result", "input.idf"]
        if weather_file:
            self.run_parameters = ["-w", weather_file] + self.run_parameters
        try:
            self.idf = IDF(idf_file_name)
        except Exception:
            raise ValueError("IDF file is damaged or not match with your EnergyPlus version.")

        # Flags for completed warmups: based on EMS documentation
        self.warmup_design_complete = False
        self.warmup_run_complete = False
        self.after_warmup_call_num = 1
        self.warmup_complete = False

        # Set Agent and controller vars
        self.agent = agent
        self.last_action = None
        self.last_state = None
        self.total_reward = 0
        self.state_name = state_name
        self.start_time = None
        self.step = step
#         self.queue = EventQueue()

        # Set Episodic Variables
        self.max_episodes = max_episodes
        self.max_episode_steps = max_episode_steps
        self.i_episode = 0
        self.i_episode_step = 0
        self.i_timestep = 0

        # set dicts to control energy plus naming
        self.eplus_naming_dict = eplus_naming_dict
        self.eplus_var_types = eplus_var_types

    def get_date(self):
        year = self.year
        month = self.api.exchange.month()
        day = self.api.exchange.day_of_month()
        hour = self.api.exchange.hour()
        minute = self.api.exchange.minutes()
        return year, month, day, hour, minute

    def get_observation(self):
        obs_dict = {}
        for entry in self.idf.idfobjects['OUTPUT:VARIABLE']:
            # we only care about the output vars for Gnu-RL
            if (entry['Variable_Name'], entry['Key_Value']) in self.eplus_naming_dict.keys():
                var_name = entry['Variable_Name']

                # if the key value is not associated with a zone return None for variable handler
                # key_val = entry['Key_Value'] if entry['Key_Value'] != '*' else None
                if entry['Key_Value'] == '*':
                    key_val = self.eplus_var_types[var_name]
                else:
                    key_val = entry['Key_Value']
                handle = self.api.exchange.get_variable_handle(var_name, key_val)
                # name the state value based on Gnu-RL paper
                key = self.eplus_naming_dict.get((var_name, entry['Key_Value']))
                obs_dict[key] = self.api.exchange.get_variable_value(handle)

        state = torch.tensor([obs_dict[name] for name in self.state_name]).unsqueeze(0).double()

        if self.start_time is None:
            self.start_time = pd.datetime(
                year=self.year, month=self.api.exchange.month(), day=self.api.exchange.day_of_month())
            cur_time = self.start_time
        else:
            cur_time = self.start_time + pd.Timedelta(seconds=self.step * (self.i_timestep+1))
        observation = (state, obs_dict, obs_dict, cur_time)
        return observation

    def get_reward(self, obs_dict):
        reward = r_func(obs_dict, self.last_action, self.agent.learner.eta)
        return reward

    def is_terminal(self):
        return self.i_episode_step == (self.max_episode_steps-1)
        # if self.i_episode_step == (self.max_episode_steps-1):
        #     return True
        # else:
        #     return False

    # def trigger_events(self):
    #     events = self.queue.trigger(self.i_timestep)
    #     for key in events["actuator"]:
    #         component_type, control_type, actuator_key = key.split("|*|")
    #         value = events["actuator"][key][1]
    #         handle = self.api.exchange.get_actuator_handle(component_type, control_type, actuator_key)
    #         self.api.exchange.set_actuator_value(handle, value)
    #     for key in events["global"]:
    #         var_name = key
    #         value = events["global"][key][1]
    #         handle = self.api.exchange.get_global_handle(var_name)
    #         self.api.exchange.set_global_value(handle, value)

    def env_make(self):
        """ Wait until the warmup periods are complete before starting simulation """
        if not self.api.exchange.api_data_fully_ready():
            return
        self.warmup_complete = True
        self.last_state = self.get_observation()

    def env_reset(self):
        """ Resets the environment and returns an initial observation

        In our episodic case every episode is a day, so the environment is not reset.
        The initial observation just needs to be returned.
        """
        if not self.api.exchange.api_data_fully_ready():
            return
        if not self.warmup_complete:
            return
        if self.i_episode >= self.max_episodes:
            return

        if self.i_episode_step == 0:
            self.last_action = self.agent.agent_start(self.last_state, self.i_episode)

    def env_action(self):
        """ Trigger actions using EMS actuators

        """
        if not self.api.exchange.api_data_fully_ready():
            return
        if not self.warmup_complete:
            return
        if self.i_episode >= self.max_episodes:
            return

        action, SAT_stpt = self.last_action

        handle = self.api.exchange.get_actuator_handle(
            self.component_type,
            self.control_type,
            self.actuator_key)

        if handle == -1:
            raise ValueError('Actuator handle could not be found')

        self.api.exchange.set_actuator_value(handle, SAT_stpt)

        # self.queue.schedule_event(SAT_stpt, self.i_timestep+1, 0,
        #                           component_type=component_type,
        #                           control_type=control_type,
        #                           actuator_key=actuator_key)
        #
        # self.trigger_events()


    def env_step(self):
        """ Takes an action and triggers agent afterwards

        Returns:
            observation: object
            reward: float
            done: boolean
            info: dict
        """
        if not self.api.exchange.api_data_fully_ready():
            return
        if not self.warmup_complete:
            return
        if self.i_episode >= self.max_episodes:
            return


        self.last_state = self.get_observation()

        handle_act = self.api.exchange.get_actuator_handle(
            self.component_type, self.control_type, self.actuator_key)
        val_act = self.api.exchange.get_actuator_value(handle_act)

        handle_obv = self.api.exchange.get_variable_handle(
            'System Node Temperature', 'VAV SYS 1 OUTLET NODE')

        val_obvs = self.api.exchange.get_variable_value(handle_obv)
        # print(val_act, val_obvs, self.last_state[1]['Indoor Temp.'])
        # pdb.set_trace()

        reward = self.get_reward(self.last_state[1])
        term = self.is_terminal()

        handle = self.api.exchange.get_actuator_handle(
            self.component_type, self.control_type, self.actuator_key)
        val = self.api.exchange.get_actuator_value(handle)
        # print('actuator value in step function', val)

        if term:
            self.agent.agent_end(reward, self.last_state, self.i_episode)
            self.i_episode += 1
            self.i_episode_step = 0
        else:
            self.last_action = self.agent.agent_step(reward, self.last_state)
            self.i_episode_step += 1

        self.i_timestep += 1

    def simulate(self):
        from pyenergyplus.api import EnergyPlusAPI

        self.idf.saveas("input.idf")
        self.api = EnergyPlusAPI()
        self.api.runtime.callback_after_new_environment_warmup_complete(self.env_make)
        self.api.runtime.callback_begin_system_timestep_before_predictor(self.env_reset)
        # self.api.runtime.callback_begin_zone_timestep_before_init_heat_balance(self.env_action)
        # self.api.runtime.callback_after_predictor_before_hvac_managers(self.env_action)
        self.api.runtime.callback_begin_system_timestep_before_predictor(self.env_action)
        self.api.runtime.callback_end_zone_timestep_after_zone_reporting(self.env_step)
        status = self.api.runtime.run_energyplus(self.run_parameters)
        print('Simulator return status: ', status)
