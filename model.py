import sys

from eventqueue import EventQueue
from eppy.modeleditor import IDF
from eppy.bunch_subclass import BadEPFieldError
# from pyenergyplus.api import EnergyPlusAPI
from multiprocessing import Event, Pipe, Process
import os


class Agent:
    """
    Dummy agent as a placeholder. No meaning
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
        :param path: The installation path of the EnergyPlus 9.3.0.
        :return: None.
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
                 agent: Agent = None
                 ):
        """
        Initialize the building by loading the IDF file to the model.
        :param idf_file_name: The relative path to the IDF file. Use it if you want to use your own model.
        :param prototype: Either "multi" and "single", indicates the Multi-family low-rise apartment building and Single-family detached house.
        :param climate_zone: The climate zone code of the building. Please refer to https://codes.iccsafe.org/content/iecc2018/chapter-3-ce-general-requirements.
        :param weather_file: The relative path to the weather file associate with the building.
        :param heating_type: Select one from "electric", "gas", "oil", and "pump"
        :param foundation_type: Select one from "crawspace", "heated", "slab", and "unheated"
        :param agent: The user-defined Agent class object if the agent is implemented in a class.
        """
        if not Model.model_import_flag:
            raise ImportError("You have to set the energyplus folder first")
        self.api = None
        self.current_state = dict()
        self.idf = None
        self.run_parameters = None
        self.queue = EventQueue()
        self.agent = agent
        self.ignore_list = set()
        self.zone_names = None
        self.thermal_names = None
        self.counter = 0
        self.historical_values = list()
        self.warmup_complete = False
        self.terminate = False
        self.wait_for_step = Event()
        self.wait_for_state = Event()
        self.parent, self.child_energy = Pipe(duplex=True)
        self.child = None
        self.use_lock = False

        # TODO: Validate input parameters

        if idf_file_name is None:
            idf_file_name = f"./buildings/{prototype}_{climate_zone}_{heating_type}_{foundation_type}.idf"
            if weather_file is None:
                weather_file = f"./weathers/{climate_zone}.epw"

        self.run_parameters = ["-d", "result", "input.idf"]
        if weather_file:
            self.run_parameters = ["-w", weather_file] + self.run_parameters

        try:
            self.idf = IDF(idf_file_name)
        except:
            raise ValueError("IDF file is damaged or not match with your EnergyPlus version.")

    @staticmethod
    def name_reformat(name):
        """
        Convert the entry from the space separated entry to the underline separated entry to match the IDF.
        :param name: The space separated entry.
        :return: The underline separated entry.
        """
        name = name.replace(' ', '_').split('_')
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
        :param idf_header_name: The type of the component.
        :return: List of settings entry.
        """
        if not self.idf.idfobjects.get(idf_header_name):
            raise KeyError(f"No {idf_header_name} section in current IDF file")
        return self.idf.idfobjects[idf_header_name][0].fieldnames

    def get_available_names_under_group(self,
                                        idf_header_name: str):
        """
        Given the type of components, find all available components in the building by their entry.
        :param idf_header_name: The type of the component.
        :return: List of names.
        """
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
        :param idf_header_name: The type of the component.
        :param component_name: The entry of the component.
        :return: Settings of this component.
        """
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
        :param idf_header_name: The type of the component.
        :param field_name: The setting entry.
        :param validate: Set to True to check the current value is valid or not.
        :return: Validation result or the range of all acceptable values retrieved from the IDD file.
        """
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
        :param idf_header_name: The type of the component.
        :param values: A dictionary map the setting entry and the setting value.
        :return: The new component.
        """
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
        :param idf_header_name: The type of the component.
        :param component_name: The entry of the component.
        :return: None.
        """
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
        :param idf_header_name: The type of the component.
        :param identifier: A dictionary map the setting entry and the setting value to locate the target component.
        :param update_values: A dictionary map the setting entry and the setting value that needs to update.
        :return: None.
        """
        if not self.idf.idfobjects.get(idf_header_name):
            raise KeyError(f"No {idf_header_name} section in current IDF file")
        fields = self.get_sub_configuration(idf_header_name)
        for entry in self.idf.idfobjects[idf_header_name]:
            valid = True
            for key, value in identifier:
                key = Model.name_reformat(key)
                if key in fields:
                    if entry[key] != value:
                        valid = False
            if valid:
                for key, value in update_values:
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
        self.thermal_names = list()
        for zone in people_zones:
            try:
                if zone[Model.name_reformat("Thermal Comfort Model 1 Type")]:
                    self.thermal_names.append(zone["Name"])
            except BadEPFieldError:
                pass

    def save_idf_file(self,
                      path: str):
        """
        Save the modified building model for EnergyPlus simulation
        :param path: The relative path to the modified IDF file.
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
        Get the state value at each timestep, and modify the building model based on the actions from the `EventQueue'.
        :return: None
        """
        if not self.api.exchange.api_data_fully_ready() or not self.warmup_complete:
            return
        current_state = dict()
        # print("Child: Simulating")
        current_state["temperature"] = dict()
        current_state["occupancy"] = dict()
        for name in self.zone_names:
            handle = self.api.exchange.get_variable_handle("Zone Air Temperature", name)
            current_state["temperature"][name] = self.api.exchange.get_variable_value(handle)
        handle = self.api.exchange.get_meter_handle("Heating:EnergyTransfer")
        current_state["energy"] = self.api.exchange.get_meter_value(handle)

        if "Zone Thermal Comfort Fanger Model PMV" in self.get_available_names_under_group("Output:Variable"):
            current_state["PMV"] = dict()
            for zone in self.thermal_names:
                handle = self.api.exchange.get_variable_handle("Zone Thermal Comfort Fanger Model PMV", zone)
                current_state["PMV"][zone] = self.api.exchange.get_variable_value(handle)

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
            self.current_state = current_state
            self.historical_values.append(self.current_state)
            events = self.queue.trigger(self.counter)
            self.counter += 1

        # print("Child: executing actions")

        # Trigger events
        for key in events["actuator"]:
            component_type, control_type, actuator_key = key.split("|*|")
            value = events["actuator"][key][1]
            handle = self.api.exchange.get_actuator_handle(component_type, control_type, actuator_key)
            self.api.exchange.set_actuator_value(handle, value)
        for key in events["global"]:
            var_name = key
            value = events["global"][key][1]
            handle = self.api.exchange.get_global_handle(var_name)
            self.api.exchange.set_global_value(handle, value)

        # if self.use_lock:
        #     # wait for next call of step
        #     self.wait_for_step.clear()
        #     self.wait_for_step.wait()
        # else:
        if not self.use_lock and self.agent:
            self.agent.step(self.current_state, self.queue, self.counter - 1)

    def step(self, action_list: list):
        """
        Add all actions into the `EventQueue', and then generate the state value of the next timestep.
        :param action_list: list of dictionarys contains the arguments for `EventQueue.schedule_event()'.
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
        if current_state != "Terminated":
            self.current_state = current_state
            self.historical_values.append(self.current_state)
        else:
            self.terminate = True
            self.child.join()
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
        self.queue = EventQueue()
        self.historical_values = list()
        self.ignore_list = set()
        self.wait_for_state.clear()
        self.wait_for_step.clear()
        self.terminate = False
        self.use_lock = True
        self.parent, self.child_energy = Pipe(duplex=True)
        self.child = Process(target=self.simulate)
        self.child.start()
        self.wait_for_state.wait()
        self.current_state = self.parent.recv()
        self.historical_values.append(self.current_state)
        self.wait_for_state.clear()
        return self.current_state

    def simulate(self, terminate_after_warmup=False):
        """
        Run the whole simulation once. If user use this method instead of the reset function, the user need to provide the Agent.
        :param terminate_after_warmup: True if the simulation should terminate after the warmup.
        :return: None.
        """
        from pyenergyplus.api import EnergyPlusAPI

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
        if self.use_lock:
            self.child_energy.send("Terminated")
            self.wait_for_state.set()

    def _init_simulation(self):
        """
        Save the modified building model and initialize the zones for states.
        :return: None.
        """
        self.idf.saveas("input.idf")
        self.use_lock = False
        self.zone_names = self.get_available_names_under_group("Zone")
        self._get_thermal_names()
        self.warmup_complete = False

    def get_current_state_values(self):
        """
        Find the current entries in the state.
        :return: List of entry names that is currently available in the state.
        """
        state_values = list(set(self.get_possible_state_entries()) - self.ignore_list)
        state_values.sort()
        return state_values

    def select_state_values(self, entry=None, index=None):
        """
        Select interested state entries. If selected entry is not available for the current building, it will be ignored.
        :param entry: Entry names that the state of the environment should have.
        :param index: Index of all available entries that the state of the environment should have.
        :return: None.
        """
        current_state = self.get_current_state_values()
        if entry is None:
            entry = list()
        elif isinstance(entry, str):
            entry = list(entry)
        if index is not None:
            if isinstance(index, int):
                index = [index]
            for i in index:
                if i < len(current_state):
                    entry.append(current_state[i])
        self.ignore_list = set(self.get_possible_state_entries()) - set(entry)

    def add_state_values(self, entry):
        """
        Add entries to the state. If selected entry is not available for the current building, it will be ignored.
        :param entry: Entry names that the state of the environment should have.
        :return: None.
        """
        if not self.ignore_list:
            return
        if isinstance(entry, str):
            entry = [entry]

        self.ignore_list -= set(entry)

    def remove_state_values(self, entry):
        """
        Remove entries from the state. If selected entry is not available in the state, it will be ignored.
        :param entry: Entry names that the state of the environment should not have.
        :return: None.
        """
        if isinstance(entry, str):
            entry = [entry]
        self.ignore_list = self.ignore_list.union(set(entry))

    def pop_state_values(self, index):
        """
        Remove entries from the state by its index. If selected index is not available in the state, it will be ignored.
        :param index: Entry index that the state of the environment should not have.
        :return: All entry names that is removed.
        """
        current_state = self.get_current_state_values()
        pop_values = list()
        if isinstance(index, int):
            index = [index]
        for i in index:
            if i < len(current_state):
                self.ignore_list.add(current_state[i])
                pop_values.append(current_state[i])

        return pop_values

    def get_possible_state_entries(self):
        """
        Get all available state entries. This list of entries only depends on the building architecture.
        :return: List of available state entry names.
        """

        output = self.get_available_names_under_group("Output:Variable")
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
