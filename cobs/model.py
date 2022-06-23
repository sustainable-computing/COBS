import sys

from cobs import EventQueue, ReplayBuffer
from eppy.modeleditor import IDF
from eppy.bunch_subclass import BadEPFieldError
from multiprocessing import Event, Pipe, Process
import os
from datetime import datetime, timedelta
from cobs.state_modifier import StateModifier
from calendar import isleap


class Agent:
    """
    Dummy agent as a placeholder. No meaning
    """

    def __init__(self):
        pass


class Reward:
    """
    Dummy reward as a placeholder. No meaning
    """

    def __init__(self):
        pass


class Model:
    """
    The environment class.
    """
    model_import_flag = False

    @classmethod
    def set_energyplus_folder(cls, path):
        """
        Add the pyenergyplus into the path so the program can find the EnergyPlus.

        :parameter path: The installation path of the EnergyPlus 9.3.0.
        :type path: str

        :return: None
        """
        sys.path.insert(0, path)
        IDF.setiddname(f"{path}Energy+.idd")
        cls.model_import_flag = True

    def __init__(self,
                 idf_file_name: str = None,
                 prototype: str = None,
                 climate_zone: str = None,
                 weather_file: str = None,
                 heating_type: str = None,
                 foundation_type: str = None,
                 agent: Agent = None,
                 reward=None,
                 eplus_naming_dict=None,
                 eplus_var_types=None,
                 eplus_meter_dict=None,
                 buffer_capacity=None,
                 buffer_seed=None,
                 buffer_chkpt_dir=None,
                 tmp_idf_path=None,
                 extra_run_parameters=list()):
        """
        Initialize the building by loading the IDF file to the model.

        :parameter idf_file_name: The relative path to the IDF file. Use it if you want to use your own model.
        :parameter prototype: Either "multi" and "single", indicates the Multi-family low-rise apartment building and Single-family detached house.
        :parameter climate_zone: The climate zone code of the building. Please refer to https://codes.iccsafe.org/content/iecc2018/chapter-3-ce-general-requirements.
        :parameter weather_file: The relative path to the weather file associate with the building.
        :parameter heating_type: Select one from "electric", "gas", "oil", and "pump"
        :parameter foundation_type: Select one from "crawspace", "heated", "slab", and "unheated"
        :parameter agent: The user-defined Agent class object if the agent is implemented in a class.
        :parameter reward: The user-defined reward class object that contains a reward(state, actions) method.
        :parameter eplus_naming_dict: A dictionary map the state variable name to some specified names.
        :parameter eplus_var_types: A dictionary contains the state name and the state source location.
        :parameter buffer_capacity: The maximum number of historical state, action, new_state pair store in the buffer.
        :parameter buffer_seed: The random seed when sample from the buffer.
        :parameter buffer_chkpt_dir: The location of the buffer checkpoint should save.
        """
        if not Model.model_import_flag:
            raise ImportError("You have to set the energyplus folder first")
        self.api = None
        self.current_state = dict()
        self.idf = None
        self.occupancy = None
        self.run_parameters = None
        self.queue = EventQueue()
        self.agent = agent
        self.ignore_list = set()
        self.zone_names = None
        self.thermal_names = None
        self.counter = 0
        self.replay = ReplayBuffer(buffer_capacity, buffer_seed, buffer_chkpt_dir)
        self.warmup_complete = False
        self.terminate = False
        self.wait_for_step = Event()
        self.wait_for_state = Event()
        self.parent, self.child_energy = Pipe(duplex=True)
        self.child = None
        self.use_lock = False
        self.reward = reward
        self.eplus_naming_dict = dict() if eplus_naming_dict is None else eplus_naming_dict
        self.eplus_var_types = dict() if eplus_var_types is None else eplus_var_types
        self.eplus_meter_dict = dict() if eplus_meter_dict is None else eplus_meter_dict
        self.prev_reward = None
        self.total_timestep = -1
        self.leap_weather = False
        self.state_modifier = StateModifier()
        self.environment_count = 1
        self.previous_env = 0

        # TODO: Validate input parameters

        if idf_file_name is None and climate_zone is not None:
            idf_file_name = f"./buildings/{prototype}_{climate_zone}_{heating_type}_{foundation_type}.idf"
            if weather_file is None and climate_zone is not None:
                weather_file = f"./weathers/{climate_zone}.epw"

        if tmp_idf_path is None:
            self.input_idf = "input.idf"
        else:
            self.input_idf = os.path.join(tmp_idf_path, "input.idf")

        self.run_parameters = ["-d", "result", *extra_run_parameters, self.input_idf]
        if weather_file:
            self.run_parameters = ["-w", weather_file] + self.run_parameters
            with open(weather_file, 'r') as w_file:
                for line in w_file:
                    line = line.split(',')
                    if len(line) > 3 and line[0].upper() == "HOLIDAYS/DAYLIGHT SAVINGS":
                        self.leap_weather = True if line[1].upper() == "YES" else False
                        break

        try:
            self.idf = IDF(idf_file_name)
        except:
            raise ValueError("IDF file is damaged or not match with your EnergyPlus version.")

    @staticmethod
    def name_reformat(name):
        """
        Convert the entry from the space separated entry to the underline separated entry to match the IDF.

        :parameter name: The space separated entry.

        :return: The underline separated entry.
        """
        name = name.replace(' ', '_').replace(':', '').split('_')
        return '_'.join([word for word in name])

    def list_all_available_configurations(self):
        """
        Generate a list of all type of components appeared in the current building.

        :return: list of components entry.
        """
        return list(self.idf.idfobjects.keys())

    def get_all_configurations(self):
        """
        Read the IDF file, and return the content formatted with the IDD file.

        :return: the full IDF file with names and comments aside.
        """
        return self.idf.idfobjects

    def get_sub_configuration(self,
                              idf_header_name: str):
        """
        Show all available settings for the given type of component.

        :parameter idf_header_name: The type of the component.

        :return: List of settings entry.
        """
        idf_header_name = idf_header_name.upper()
        if not self.idf.idfobjects.get(idf_header_name):
            raise KeyError(f"No {idf_header_name} section in current IDF file")
        return self.idf.idfobjects[idf_header_name][0].fieldnames

    def get_available_names_under_group(self,
                                        idf_header_name: str):
        """
        Given the type of components, find all available components in the building by their entry.

        :parameter idf_header_name: The type of the component.

        :return: List of names.
        """
        idf_header_name = idf_header_name.upper()
        available_names = self.get_sub_configuration(idf_header_name)
        if "Name" in available_names:
            return [entry["Name"] for entry in self.idf.idfobjects[idf_header_name]]
        else:
            for field_name in available_names:
                if "name" in field_name.lower():
                    return [entry[field_name] for entry in self.idf.idfobjects[idf_header_name]]
            raise KeyError(f"No entry field available for {idf_header_name}")

    def get_configuration(self,
                          idf_header_name: str,
                          component_name: str = None):
        """
        Given the type of component, the entry of the target component, find the settings of that component.

        :parameter idf_header_name: The type of the component.

        :parameter component_name: The entry of the component.

        :return: Settings of this component.
        """
        idf_header_name = idf_header_name.upper()
        if component_name is None:
            return self.idf.idfobjects[idf_header_name]
        else:
            names = self.get_available_names_under_group(idf_header_name)
            if component_name in names:
                return self.idf.idfobjects[idf_header_name][names.index(component_name)]
            else:
                raise KeyError(f"Failed to locate {component_name} in {idf_header_name}")

    def get_value_range(self,
                        idf_header_name: str,
                        field_name: str,
                        validate: bool = False):
        """
        Get the range of acceptable values of the specific setting.

        :parameter idf_header_name: The type of the component.

        :parameter field_name: The setting entry.

        :parameter validate: Set to True to check the current value is valid or not.

        :return: Validation result or the range of all acceptable values retrieved from the IDD file.
        """
        idf_header_name = idf_header_name.upper()
        field_name = field_name.replace(' ', '_')
        if field_name not in self.get_sub_configuration(idf_header_name):
            raise KeyError(f"Failed to locate {field_name} in {idf_header_name}")
        if validate:
            return self.idf.idfobjects[idf_header_name][0].checkrange(field_name)
        else:
            return self.idf.idfobjects[idf_header_name][0].getrange(field_name)

    def add_configuration(self,
                          idf_header_name: str,
                          values: dict = None):
        """
        Create and add a new component into the building model with the specific type and setting values.

        :parameter idf_header_name: The type of the component.

        :parameter values: A dictionary map the setting entry and the setting value.

        :return: The new component.
        """
        idf_header_name = idf_header_name.upper()
        object = self.idf.newidfobject(idf_header_name.upper())
        if values is None:
            return object
        for key, value in values.items():
            key = Model.name_reformat(key)
            if isinstance(value, (int, float)):
                exec(f"object.{key} = {value}")
            else:
                exec(f"object.{key} = '{value}'")
        return object

    def delete_configuration(self,
                             idf_header_name: str,
                             component_name: str = None):
        """
        Delete an existing component from the building model.

        :parameter idf_header_name: The type of the component.

        :parameter component_name: The entry of the component.

        :return: None.
        """
        idf_header_name = idf_header_name.upper()
        if not self.idf.idfobjects.get(idf_header_name):
            raise KeyError(f"No {idf_header_name} section in current IDF file")
        if component_name is None:
            while len(self.idf.idfobjects[idf_header_name]):
                self.idf.popidfobject(idf_header_name, 0)
        else:
            names = self.get_available_names_under_group(idf_header_name)
            if component_name in names:
                self.idf.popidfobject(idf_header_name, names.index(component_name))
            else:
                raise KeyError(f"Failed to locate {component_name} in {idf_header_name}")

    def edit_configuration(self,
                           idf_header_name: str,
                           identifier: dict,
                           update_values: dict):
        """
        Edit an existing component in the building model.

        :parameter idf_header_name: The type of the component.

        :parameter identifier: A dictionary map the setting entry and the setting value to locate the target component.

        :parameter update_values: A dictionary map the setting entry and the setting value that needs to update.

        :return: None.
        """
        idf_header_name = idf_header_name.upper()
        if not self.idf.idfobjects.get(idf_header_name):
            raise KeyError(f"No {idf_header_name} section in current IDF file")
        fields = self.get_sub_configuration(idf_header_name)
        for entry in self.idf.idfobjects[idf_header_name]:
            valid = True
            for key, value in identifier.items():
                key = Model.name_reformat(key)
                if key in fields:
                    if entry[key] != value:
                        valid = False
            if valid:
                for key, value in update_values.items():
                    key = Model.name_reformat(key)
                    if isinstance(value, (int, float)):
                        exec(f"entry.{key} = {value}")
                    else:
                        exec(f"entry.{key} = '{value}'")

    def _get_thermal_names(self):
        """
        Initialize all available thermal zones.

        :return: None
        """
        people_zones = self.get_configuration("People")
        self.thermal_names = dict()
        for zone in people_zones:
            try:
                if zone[Model.name_reformat("Thermal Comfort Model 1 Type")]:
                    self.thermal_names[zone["Name"]] = zone[Model.name_reformat("Zone or ZoneList Name")]
            except BadEPFieldError:
                pass

    def save_idf_file(self,
                      path: str):
        """
        Save the modified building model for EnergyPlus simulation

        :parameter path: The relative path to the modified IDF file.

        :return: None.
        """
        self.idf.saveas(path)

    def _initialization(self):
        """
        Initialize the EnergyPlus simulation by letting the EnergyPlus finish the warmup.

        :return: None
        """
        if not self.api.exchange.api_data_fully_ready():
            return
        self.warmup_complete = True

    def _generate_output_files(self):
        """
        Assert errors to terminate the simulation after the warmup in order to generate the EDD file to list all available actions for the current building.

        :return: None
        """
        assert False

    def _step_callback(self):
        """
        Get the state value at each timestep, and modify the building model based on the actions from the ``EventQueue``.

        :return: None

        """
        # print("Child: Not ready")
        if not self.api.exchange.api_data_fully_ready() or not self.warmup_complete or self.api.exchange.warmup_flag():
            return
        # print(self.api.exchange.warmup_flag())

        current_state = dict()
        # print("Child: Simulating")
        current_state["environment_id"] = int(self.api.exchange.current_environment_num())
        if self.previous_env == 0 or current_state["environment_id"] != self.previous_env:
            self.previous_env = current_state["environment_id"]
            self.counter = 0
        current_state["timestep"] = self.counter
        # print(self.get_date())
        current_state["time"] = self.get_date()
        current_state["temperature"] = dict()
        current_state["occupancy"] = dict()
        current_state["terminate"] = self.total_timestep == self.counter and \
                                     current_state["environment_id"] == self.environment_count
        # if self.occupancy is not None:
        #     current_state["occupancy"] = {zone: value[self.counter] for zone, value in self.occupancy.items()}
        for name in self.zone_names:
            handle = self.api.exchange.get_variable_handle("Zone People Occupant Count", name)
            if handle == -1:
                continue
            current_state["occupancy"][name] = self.api.exchange.get_variable_value(handle)
        for name in self.zone_names:
            handle = self.api.exchange.get_variable_handle("Zone Air Temperature", name)
            if handle == -1:
                continue
            # print("Child: Simulating 2")
            current_state["temperature"][name] = self.api.exchange.get_variable_value(handle)
        handle = self.api.exchange.get_meter_handle("Heating:EnergyTransfer")
        current_state["energy"] = self.api.exchange.get_meter_value(handle)
        if self.reward is not None:
            current_state["reward"] = self.prev_reward

        # print("Child: Simulating 1")

        if "Zone Thermal Comfort Fanger Model PMV" in self.get_available_names_under_group("Output:Variable"):
            current_state["PMV"] = dict()
            for zone in self.thermal_names:
                handle = self.api.exchange.get_variable_handle("Zone Thermal Comfort Fanger Model PMV", zone)
                if handle == -1:
                    continue
                current_state["PMV"][self.thermal_names[zone]] = self.api.exchange.get_variable_value(handle)

        # Add state values
        state_vars = self.get_current_state_variables()

        # Add for asked meter values
        for meter_name in self.eplus_meter_dict:
            handle = self.api.exchange.get_meter_handle(meter_name)
            if handle == -1:
                continue
            current_state[self.eplus_meter_dict[meter_name]] = self.api.exchange.get_meter_value(handle)

        # Add for temp extra output
        for entry in self.idf.idfobjects['OUTPUT:VARIABLE']:
            # we only care about the output vars for Gnu-RL
            if (entry['Variable_Name'], entry['Key_Value']) in self.eplus_naming_dict.keys() or \
                    (entry['Variable_Name'], entry['Key_Value']) in state_vars:
                var_name = entry['Variable_Name']

                # if the key value is not associated with a zone return None for variable handler
                # key_val = entry['Key_Value'] if entry['Key_Value'] != '*' else None
                if entry['Key_Value'] == '*':
                    key_val = self.eplus_var_types.get(var_name, None)
                    if key_val is None:
                        continue
                else:
                    key_val = entry['Key_Value']
                handle = self.api.exchange.get_variable_handle(var_name, key_val)
                if handle == -1:
                    continue
                # name the state value based on Gnu-RL paper
                key = self.eplus_naming_dict.get((var_name, entry['Key_Value']), f"{var_name}_{key_val}")
                current_state[key] = self.api.exchange.get_variable_value(handle)

        self.state_modifier.get_update_states(current_state, self)
        # current_state.update(update_dict)
        # print(current_state)

        if self.use_lock:
            # print("Child: Sending current states")
            self.child_energy.send(current_state)
            self.wait_for_state.set()
            # Take all actions
            self.wait_for_step.clear()
            # print("Child: Waiting for actions")
            if not self.child_energy.poll():
                self.wait_for_step.wait()
            # print("Child: Receiving actions")
            events = self.child_energy.recv()
        else:
            # print(self.current_state)
            if len(self.current_state) != 0 and self.current_state["environment_id"] != current_state["environment_id"]:
                self.counter = 0
                current_state["timestep"] = 0
                self.queue = EventQueue()

            if self.counter != 0:
                self.replay.push(self.current_state,
                                 self.queue.get_event(self.current_state["timestep"]),
                                 current_state,
                                 current_state["terminate"])
            self.current_state = current_state
            # self.historical_values.append(self.current_state)
            events = self.queue.trigger(self.counter)
        self.counter += 1

        # Trigger modifiers
        # for modifier in self.modifier:
        #     modifier.update(current_state)
        # print("Child: executing actions")

        # print("Child: Printing Reward")
        # Calculate Reward
        if self.reward is not None:
            self.prev_reward = self.reward.reward(current_state, events)

        # Trigger events
        for key in events["actuator"]:
            component_type, control_type, actuator_key = key.split("|*|")
            value = events["actuator"][key][1]
            handle = self.api.exchange.get_actuator_handle(component_type, control_type, actuator_key)
            if handle == -1:
                raise ValueError('Actuator handle could not be found: ', component_type, control_type, actuator_key)
            self.api.exchange.set_actuator_value(handle, value)
        for key in events["global"]:
            var_name = key
            value = events["global"][key][1]
            handle = self.api.exchange.get_global_handle(var_name)
            if handle == -1:
                raise ValueError('Actuator handle could not be found: ', var_name)
            self.api.exchange.set_global_value(handle, value)

        # if self.use_lock:
        #     # wait for next call of step
        #     self.wait_for_step.clear()
        #     self.wait_for_step.wait()
        # else:
        if not self.use_lock and self.agent:
            self.agent.step(self.current_state, self.queue, self.counter - 1)

    def step(self, action_list=None):
        """
        Add all actions into the ``EventQueue``, and then generate the state value of the next timestep.

        :parameter action_list: list of dictionarys contains the arguments for ``EventQueue.schedule_event()``.

        :return: The state value of the current timestep.
        """
        if action_list is not None:
            for action in action_list:
                self.queue.schedule_event(**action)
        # print("Parent: Sending actions")
        self.parent.send(self.queue.trigger(self.counter))
        self.counter += 1
        # Let process grab and execute actions
        # print("Parent: Releasing child's lock")
        self.wait_for_state.clear()
        self.wait_for_step.set()
        # print("Parent: Waiting for state values")
        if not self.parent.poll():
            self.wait_for_state.wait()
        self.wait_for_state.clear()
        current_state = self.parent.recv()
        # if isinstance(current_state, dict):
        if self.current_state["environment_id"] == current_state["environment_id"]:
            self.replay.push(self.current_state,
                             self.queue.get_event(self.current_state["timestep"]),
                             current_state,
                             current_state["terminate"])
        else:
            self.counter = 0
            self.queue = EventQueue()
            current_state["timestep"] = 0
        self.current_state = current_state
        # self.historical_values.append(self.current_state)
        if current_state["terminate"]:
            self.terminate = True
            self.parent.send(self.queue.trigger(self.counter))
            self.wait_for_step.set()
            self.child.join()
            # self.replay.terminate()
        self.wait_for_state.clear()
        # print("Parent: received state values")
        return self.current_state

    def is_terminate(self):
        """
        Determine if the simulation is finished or not.

        :return: True if the simulation is done, and False otherwise.
        """
        return self.terminate

    def reset(self):
        """
        Clear the actions and buffer, reset the environment and start the simulation.

        :return: The initial state of the simulation.
        """
        self._init_simulation()
        self.counter = 0
        self.total_timestep = self.get_total_timestep() - 1
        self.queue = EventQueue()
        self.replay.reset()
        # self.ignore_list = set()
        self.wait_for_state.clear()
        self.wait_for_step.clear()
        self.terminate = False
        self.use_lock = True
        self.parent, self.child_energy = Pipe(duplex=True)
        self.child = Process(target=self.simulate)
        self.child.start()
        # print("Waiting")
        if not self.parent.poll():
            self.wait_for_state.wait()
        self.current_state = self.parent.recv()
        # self.historical_values.append(self.current_state)
        self.wait_for_state.clear()
        return self.current_state

    def get_total_timestep(self):
        if "-w" not in self.run_parameters:
            return self.get_configuration("Timestep")[0].Number_of_Timesteps_per_Hour * 24 * 8
        elif len(self.get_configuration("RunPeriod")) == 0:
            raise ValueError("Your IDF files does not specify the run period."
                             "Please manually edit the IDF file or use Model().set_runperiod(...)")
        run_period = self.get_configuration("RunPeriod")[0]

        start = datetime(year=int(run_period.Begin_Year) if run_period.Begin_Year else 2000,
                         month=int(run_period.Begin_Month),
                         day=int(run_period.Begin_Day_of_Month))
        end = datetime(year=int(run_period.End_Year) if run_period.End_Year else start.year,
                       month=int(run_period.End_Month),
                       day=int(run_period.End_Day_of_Month))
        end += timedelta(days=1)

        if not self.leap_weather:
            offset = 0
            for year in range(start.year, end.year + 1):
                if isleap(year) and datetime(year, 2, 29) > start and datetime(year, 2, 29) < end:
                    offset += 1
            end -= timedelta(days=offset)

        timestep = self.get_configuration("Timestep")[0].Number_of_Timesteps_per_Hour
        if 60 % timestep != 0:
            timestep = 60 // round(60 / timestep)

        return int((end - start).total_seconds() // 3600 * timestep)

    def simulate(self, terminate_after_warmup=False):
        """
        Run the whole simulation once. If user use this method instead of the reset function, the user need to provide the Agent.

        :parameter terminate_after_warmup: True if the simulation should terminate after the warmup.

        :return: None.
        """
        from pyenergyplus.api import EnergyPlusAPI

        self.replay.set_ignore(self.state_modifier.get_ignore_by_checkpoint())
        if not self.use_lock:
            self._init_simulation()
        # for entry in self.zone_names:
        #     print(entry)
        #     self.current_handle["temperature"][entry] = \
        #         self.api.exchange.get_variable_handle("Zone Air Temperature", entry)
        # self.current_handle["temperature"] = self.api.exchange.get_variable_handle("SITE OUTDOOR AIR DRYBULB TEMPERATURE", "ENVIRONMENT")
        # self.current_handle["energy"] = self.api.exchange.get_meter_handle("Electricity:Facility")
        self.api = EnergyPlusAPI()
        if not terminate_after_warmup:
            self.api.runtime.callback_after_new_environment_warmup_complete(self._initialization)
            self.api.runtime.callback_begin_system_timestep_before_predictor(self._step_callback)
        else:
            self.api.runtime.callback_begin_new_environment(self._generate_output_files)
        self.api.runtime.run_energyplus(self.run_parameters)
        # if self.use_lock:
        #     self.child_energy.send("Terminated")
        #     self.wait_for_state.set()
        # else:
        #     self.replay.terminate()

    def _init_simulation(self):
        """
        Save the modified building model and initialize the zones for states.

        :return: None.
        """
        try:
            self.get_configuration("Output:Variable", "Zone People Occupant Count")
        except KeyError:
            self.add_configuration("Output:Variable", {"Key Value": '*',
                                                       "Variable Name": "Zone People Occupant Count",
                                                       "Reporting Frequency": "Timestep"})
        if self.get_configuration("SimulationControl")[0].Run_Simulation_for_Weather_File_Run_Periods.upper() == "NO":
            self.get_configuration("SimulationControl")[0].Run_Simulation_for_Weather_File_Run_Periods = "Yes"
        self.environment_count = self.get_num_environments()
        self.idf.saveas(self.input_idf)
        self.use_lock = False
        self.zone_names = self.get_available_names_under_group("Zone")
        self._get_thermal_names()
        self.warmup_complete = False

    def get_current_state_variables(self):
        """
        Find the current entries in the state.

        :return: List of entry names that is currently available in the state.
        """
        state_values = list(set(self.get_possible_state_variables()) - self.ignore_list)
        state_values.sort()
        return state_values

    def select_state_variables(self, entry=None, index=None):
        """
        Select interested state entries. If selected entry is not available for the current building, it will be ignored.

        :parameter entry: Entry names and corresponding objects that the state of the environment should have.

        :parameter index: Index of all available entries that the state of the environment should have.

        :return: None.
        """
        current_state = self.get_current_state_variables()
        if entry is None:
            entry = list()
        elif isinstance(entry, tuple):
            entry = list(entry)
        if index is not None:
            if isinstance(index, int):
                index = [index]
            for i in index:
                if i < len(current_state):
                    entry.append(current_state[i])
        self.ignore_list = set(self.get_possible_state_variables()) - set(entry)

    def add_state_variables(self, entry):
        """
        Add entries to the state. If selected entry is not available for the current building, it will be ignored.

        :parameter entry: Entry names and corresponding objects that the state of the environment should have.

        :return: None.
        """
        if not self.ignore_list:
            return
        if isinstance(entry, tuple):
            entry = [entry]

        self.ignore_list -= set(entry)

    def remove_state_variables(self, entry):
        """
        Remove entries from the state. If selected entry is not available in the state, it will be ignored.

        :parameter entry: Entry names and corresponding objects that the state of the environment should not have.

        :return: None.
        """
        if isinstance(entry, tuple):
            entry = [entry]
        self.ignore_list = self.ignore_list.union(set(entry))

    def pop_state_variables(self, index):
        """
        Remove entries from the state by its index. If selected index is not available in the state, it will be ignored.

        :parameter index: Entry index that the state of the environment should not have.

        :return: All entry names that is removed.
        """
        current_state = self.get_current_state_variables()
        pop_values = list()
        if isinstance(index, int):
            index = [index]
        for i in index:
            if i < len(current_state):
                self.ignore_list.add(current_state[i])
                pop_values.append(current_state[i])

        return pop_values

    def get_possible_state_variables(self):
        """
        Get all available state entries. This list of entries only depends on the building architecture.

        :return: List of available state entry names.
        """

        output = [(var["Variable_Name"], var["Key_Value"])
                  for var in self.get_configuration("Output:Variable") if var["Key_Value"] != "*"]
        output.sort()
        return output

    def get_possible_actions(self):
        """
        Get all available actions that the user-defined agent can take. This list of actions only depends on the building architecture.

        :return: List of available actions in dictionaries.
        """
        if not os.path.isfile("./result/eplusout.edd"):
            if not self.get_configuration("Output:EnergyManagementSystem"):
                self.add_configuration("Output:EnergyManagementSystem",
                                       values={"Actuator Availability Dictionary Reporting": "Verbose",
                                               "Internal Variable Availability Dictionary Reporting": "Verbose",
                                               "EMS Runtime Language Debug Output Level": "ErrorsOnly"})
            try:
                self.simulate(terminate_after_warmup=True)
            except AssertionError:
                pass

        actions = list()
        with open("./result/eplusout.edd", 'r') as edd:
            for line in edd:
                line = line.strip()
                if len(line) == 0 or line[0] == '!':
                    continue
                line = line.split(',')
                actions.append({"Component Type": line[2],
                                "Control Type": line[3],
                                "Actuator Key": line[1]})
        return actions

    def get_num_environments(self):
        """
        Calculate the number of environments the current IDF file defined. Each "SizingPeriod:DesignDay",
        "SizingPeriod:WeatherFileDays", and "SizingPeriod:WeatherFileConditionType" are an environment.

        :return: An integer indicates the total number of environments.
        """
        return sum([len(self.get_configuration(objects)) for objects in ("SizingPeriod:DesignDay",
                                                                         "SizingPeriod:WeatherFileDays",
                                                                         "SizingPeriod:WeatherFileConditionType")]) + 1

    def get_link_zones(self):
        """
        Generate a graph that shows the connectivity of zones of the current building.

        :return: A bi-directional graph represented by a dictionary where the key is the source zone name and the value is a set of all neighbor zone name.
        """
        link_zones = {"Outdoor": set()}

        wall_to_zone = {}
        walls = self.get_configuration("BuildingSurface:Detailed")
        for wall in walls:
            if wall.Surface_Type != "WALL":
                continue
            wall_to_zone[wall.Name] = wall.Zone_Name
            link_zones[wall.Zone_Name] = set()
        for wall in walls:
            if wall.Surface_Type != "WALL":
                continue
            if wall.Outside_Boundary_Condition == "Outdoors":
                link_zones[wall.Zone_Name].add("Outdoor")
                link_zones["Outdoor"].add(wall.Zone_Name)
            elif wall.Outside_Boundary_Condition_Object:
                link_zones[wall_to_zone[wall.Outside_Boundary_Condition_Object]].add(wall.Zone_Name)
                link_zones[wall.Zone_Name].add(wall_to_zone[wall.Outside_Boundary_Condition_Object])

        return link_zones

    def get_date(self):
        """
        Get the current time in the simulation environment.

        :return: None
        """
        year = self.api.exchange.year()
        month = self.api.exchange.month()
        day = self.api.exchange.day_of_month()
        hour = self.api.exchange.hour()
        minute = self.api.exchange.minutes()
        current_time = datetime(year, month, day, hour) + timedelta(minutes=minute)
        return current_time

    def get_windows(self):
        """
        Get the zone-window matching dictionary based on the IDF file.

        :return: A dictionary where key is the zone name, and the value is a set of window available in the zone.
        """
        zone_window = {name: set() for name in self.get_available_names_under_group("Zone")}
        all_window = dict()
        for window in self.get_configuration("FenestrationSurface:Detailed"):
            if window.Surface_Type.upper() != "WINDOW":
                continue
            if window.Building_Surface_Name not in all_window:
                all_window[window.Building_Surface_Name] = list()
            all_window[window.Building_Surface_Name].append(window.Name)

        for wall in self.get_configuration("BuildingSurface:Detailed"):
            if wall.Surface_Type.upper() != "WALL":
                continue
            if wall.Name in all_window:
                for name in all_window[wall.Name]:
                    zone_window[wall.Zone_Name].add(name)
        return zone_window

    def get_doors(self):
        """
        Get the zone-door matching dictionary based on the IDF file.

        :return: A dictionary where key is the zone name, and the value is a set of door available in the zone.
        """
        zone_door = {name: set() for name in self.get_available_names_under_group("Zone")}
        all_door = dict()
        for door in self.get_configuration("FenestrationSurface:Detailed"):
            if door.Surface_Type != "GLASSDOOR":
                continue
            all_door[door.Building_Surface_Name] = door.Name

        for wall in self.get_configuration("BuildingSurface:Detailed"):
            if wall.Surface_Type != "WALL":
                continue
            if wall.Name in all_door:
                zone_door[wall.Zone_Name].add(all_door[wall.Name])
        return zone_door

    def get_lights(self):
        """
        Get the zone-light matching dictionary based on the IDF file.

        :return: A dictionary where key is the zone name, and the value is a set of light available in the zone.
        """
        zone_light = {name: set() for name in self.get_available_names_under_group("Zone")}
        for light in self.get_configuration("Lights"):
            zone_light[light.Zone_or_ZoneList_Name].add(light.Name)
        return zone_light

    def get_blinds(self):
        """
        Get the zone-blind matching dictionary based on the IDF file.

        :return: A dictionary where key is the zone name, and the value is a set of blind available in the zone.
        """
        window_with_blinds = set()
        for shade in self.get_configuration("WindowShadingControl"):
            window_with_blinds.add(shade.Fenestration_Surface_1_Name)

        zone_blinds = self.get_windows()
        for zone in zone_blinds:
            zone_blinds[zone] = zone_blinds[zone].intersection(window_with_blinds)

        return zone_blinds

    def set_blinds(self, windows, blind_material_name=None, shading_control_type='AlwaysOff', setpoint=50,
                   agent_control=False):
        """
        Install blinds that can be controlled on some given windows.

        :param windows: An iterable object that includes all windows' name that plan to install the blind.
        :param blind_material_name: The name of an existing blind in the IDF file  as the blind for all windows.
        :param shading_control_type: Specify default EPlus control strategy (only works if control=False)
        :param setpoint: Specify default blind angle.
        :param agent_control: False if using a default EPlus control strategy or no control (ie blinds always off). True if using an external agent to control the blinds.
        :return: None
        """
        if agent_control:
            shading_control_type = 'OnIfScheduleAllows'

        blind_material = None
        if blind_material_name:
            try:
                blind_material = self.get_configuration("WindowMaterial:Blind", blind_material_name)
            except KeyError:
                pass

        zone_window = self.get_windows()

        for zone in zone_window:
            for window in zone_window[zone]:
                if window in windows:
                    window_idf = self.get_configuration("FenestrationSurface:Detailed", window)
                    if blind_material is None:
                        blind = {"Name": f"{window}_blind",
                                 "Slat Orientation": "Horizontal",
                                 "Slat Width": 0.025,
                                 "Slat Angle": setpoint,
                                 "Slat Separation": 0.01875,
                                 "Front Side Slat Beam Solar Reflectance": 0.8,
                                 "Back Side Slat Beam Solar Reflectance": 0.8,
                                 "Front Side Slat Diffuse Solar Reflectance": 0.8,
                                 "Back Side Slat Diffuse Solar Reflectance": 0.8,
                                 "Slat Beam Visible Transmittance": 0.0}
                        blind_mat = self.add_configuration("WindowMaterial:Blind", values=blind)
                    else:
                        blind_mat = self.idf.copyidfobject(blind_material)
                        blind_mat.Name = blind_mat.Name + f" {window}"

                    shading = {"Name": f"{window}_blind_shading",
                               "Zone Name": zone,
                               "Shading Type": "InteriorBlind",
                               "Shading Device Material Name": f"{blind_mat.Name}",
                               "Shading Control Type": shading_control_type,
                               "Setpoint": setpoint,
                               "Type of Slat Angle Control for Blinds": "FixedSlatAngle",
                               "Fenestration Surface 1 Name": window_idf.Name}

                    if agent_control:
                        shading["Type of Slat Angle Control for Blinds"] = "ScheduledSlatAngle"
                        shading["Slat Angle Schedule Name"] = f"{window}_shading_schedule"
                        shading["Multiple Surface Control Type"] = "Group"
                        shading["Shading Control Is Scheduled"] = "Yes"
                        angle_schedule = {"Name": f"{window}_shading_schedule",
                                          "Schedule Type Limits Name": "Angle",
                                          "Hourly Value": 45}
                        self.add_configuration("Schedule:Constant", values=angle_schedule)

                    self.add_configuration("WindowShadingControl", values=shading)

    def set_occupancy(self, occupancy, locations):
        """
        Include the occupancy schedule generated by the OccupancyGenerator to the model as the occupancy data in
        EnergyPlus simulated environment is broken.

        :param occupancy: Numpy matrix contains the number of occupanct in each zone at each time slot.
        :param locations: List of zone names.
        :return: None
        """
        occupancy = occupancy.astype(int)
        self.occupancy = {locations[i]: occupancy[i, :] for i in range(len(locations))}
        if "Outdoor" in self.occupancy.keys():
            self.occupancy.pop("Outdoor")
        if "busy" in self.occupancy.keys():
            self.occupancy.pop("busy")

    def set_runperiod(self,
                      days,
                      start_year: int = 2000,
                      start_month: int = 1,
                      start_day: int = 1,
                      specify_year: bool = False):
        """
        Set the simulation run period.

        :param days: How many days in total the simulation should perform.
        :param start_year: Start from which year
        :param start_month: Start from which month of the year
        :param start_day: Start from which day of the month
        :param specify_year: Use default year or a specific year when simulation is within a year.
        :return: None
        """
        if "-w" not in self.run_parameters:
            raise KeyError("You must include a weather file to set run period")
        start = datetime(start_year, start_month, start_day)
        end = start + timedelta(days=days - 1)
        if not self.leap_weather:
            test_year = start_year - 1
            while datetime(test_year, 1, 1) < end:
                test_year += 1
                if not isleap(test_year):
                    continue
                if datetime(test_year, 2, 29) > start and datetime(test_year, 2, 29) < end:
                    end += timedelta(days=1)

        values = {"Begin Month": start_month,
                  "Begin Day of Month": start_day,
                  "End Month": end.month,
                  "End Day of Month": end.day}
        if end.year != start_year or specify_year:
            values.update({"Begin Year": start_year,
                           "End Year": end.year})
        run_setting = self.get_configuration("RunPeriod")
        if len(run_setting) == 0:
            values["Name"] = "RunPeriod 1"
            self.add_configuration("RunPeriod", values)
        else:
            name = self.get_configuration("RunPeriod")[0].Name
            self.edit_configuration("RunPeriod", {"Name": name}, values)

    def set_timestep(self, timestep_per_hour):
        """
        Set the timestep per hour for the simulation.

        :param timestep_per_hour: How many timesteps within a hour.
        :return: None
        """
        self.get_configuration("Timestep")[0].Number_of_Timesteps_per_Hour = timestep_per_hour

    def add_state_modifier(self, model):
        """
        Add a state modifier model, including predictive model, state estimator, controller, etc.

        :param model: A class object that follows the template (contains step(true_state, environment) method).
        :return: None
        """
        self.state_modifier.add_model(model)

    def flatten_state(self, order, state=None):
        """
        Flatten the state to a list of values by a given order.

        :param order: The order that the values should follow.
        :param state: The state to flatten. If not specified, then the current state is selected.
        :return: List of values follows the given order.
        """
        if state is None:
            state = self.current_state
        return [self.current_state.get(name, None) for name in order]

    def sample_buffer(self, batch_size):
        """
        Sample a batch of experience from the replay buffer.

        :param batch_size: Number of entries in a batch.
        :return: (state, action, next state, is terminate)
        """
        return self.replay.sample(batch_size)

    def sample_flattened_buffer(self, order, batch_size):
        """
        Sample a batch of experience from the replay buffer and flatten the states by a given order.

        :param order: The order that the values should follow.
        :param batch_size: Number of entries in a batch.
        :return: (state, action, next state, is terminate) where states are flatten.
        """
        state, action, next_state, done = self.replay.sample(batch_size)
        for i, row in state:
            state[i] = self.flatten_state(order, row)
        for i, row in next_state:
            next_state[i] = self.flatten_state(order, row)
        return state, action, next_state, done
