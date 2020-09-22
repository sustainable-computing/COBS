import sys

from eventqueue import EventQueue
from eppy.modeleditor import IDF
from eppy.bunch_subclass import BadEPFieldError
# from pyenergyplus.api import EnergyPlusAPI
from multiprocessing import Event, Pipe, Process
import os


class Agent:
    def __init__(self):
        pass

class Model:
    model_import_flag = False

    @classmethod
    def set_energyplus_folder(cls, path):
        sys.path.insert(0, path)
        IDF.setiddname(f"{path}Energy+.idd")
        cls.model_import_flag = True

    def __init__(self,
                 idf_file_name: str = None,
                 basement_type: str = None,
                 prototype: str = None,
                 climate_zone: str = None,
                 weather_file: str = None,
                 heating_type: str = None,
                 foundation_type: str = None,
                 agent: Agent = None
                 ):
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
        self.parent, self.child_energy = Pipe(duplex=False)
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
        name = name.replace(' ', '_').split('_')
        return '_'.join([word for word in name])

    def list_all_available_configurations(self):
        return list(self.idf.idfobjects.keys())

    def get_all_configurations(self):
        return self.idf.idfobjects

    def get_sub_configuration(self,
                              idf_header_name: str):
        if not self.idf.idfobjects.get(idf_header_name):
            raise KeyError(f"No {idf_header_name} section in current IDF file")
        return self.idf.idfobjects[idf_header_name][0].fieldnames

    def get_available_names_under_group(self,
                                        idf_header_name: str):
        available_names = self.get_sub_configuration(idf_header_name)
        if "Name" in available_names:
            return [entry["Name"] for entry in self.idf.idfobjects[idf_header_name]]
        else:
            for field_name in available_names:
                if "name" in field_name.lower():
                    return [entry[field_name] for entry in self.idf.idfobjects[idf_header_name]]
            raise KeyError(f"No name field available for {idf_header_name}")

    def get_configuration(self,
                          idf_header_name: str,
                          component_name: str = None):
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

    def get_thermal_names(self):
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
        self.idf.saveas(path)

    def validate(self):
        pass

    def initialization(self):
        if not self.api.exchange.api_data_fully_ready():
            return
        self.warmup_complete = True

    def generate_output_files(self):
        assert False

    def step_callback(self):
        if not self.api.exchange.api_data_fully_ready() or not self.warmup_complete:
            return
        current_state = dict()

        current_state["temperature"] = dict()
        current_state["occupancy"] = dict()
        for name in self.zone_names:
            handle = self.api.exchange.get_variable_handle("Zone Air Temperature", name)
            current_state["temperature"][name] = self.api.exchange.get_variable_value(handle)
        handle = self.api.exchange.get_meter_handle("Heating:EnergyTransfer")
        current_state["electricity"] = self.api.exchange.get_meter_value(handle)

        if "Zone Thermal Comfort Fanger Model PMV" in self.get_available_names_under_group("Output:Variable"):
            current_state["PMV"] = dict()
            for zone in self.thermal_names:
                handle = self.api.exchange.get_variable_handle("Zone Thermal Comfort Fanger Model PMV", zone)
                current_state["PMV"][zone] = self.api.exchange.get_variable_value(handle)

        if self.use_lock:
            self.child_energy.send(current_state)
            self.wait_for_state.set()
            # Take all actions
            self.wait_for_step.clear()
            self.wait_for_step.wait()

            events = self.child_energy.recv()
        else:
            self.current_state = current_state
            self.historical_values.append(self.current_state)
            events = self.queue.trigger(self.counter)
            self.counter += 1

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
        if action_list is not None:
            for action in action_list:
                self.queue.schedule_event(**action)
        self.parent.send(self.queue.trigger(self.counter))
        self.counter += 1
        # Let process grab and execute actions
        self.wait_for_state.clear()
        self.wait_for_step.set()
        self.wait_for_state.wait()
        self.wait_for_state.clear()
        current_state = self.parent.recv()
        if self.current_state != "Terminated":
            self.current_state = current_state
            self.historical_values.append(self.current_state)
        else:
            self.terminate = True
        self.wait_for_state.clear()
        return self.current_state

    def is_terminate(self):
        return self.terminate

    def reset(self):
        self.init()
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

    def simulate(self, get_output_files_only=False):
        from pyenergyplus.api import EnergyPlusAPI

        if not self.use_lock:
            self.init()
        # for name in self.zone_names:
        #     print(name)
        #     self.current_handle["temperature"][name] = \
        #         self.api.exchange.get_variable_handle("Zone Air Temperature", name)
        # self.current_handle["temperature"] = self.api.exchange.get_variable_handle("SITE OUTDOOR AIR DRYBULB TEMPERATURE", "ENVIRONMENT")
        # self.current_handle["electricity"] = self.api.exchange.get_meter_handle("Electricity:Facility")
        self.api = EnergyPlusAPI()
        if not get_output_files_only:
            self.api.runtime.callback_after_new_environment_warmup_complete(self.initialization)
            self.api.runtime.callback_begin_system_timestep_before_predictor(self.step_callback)
        else:
            self.api.runtime.callback_begin_new_environment(self.generate_output_files)
        self.api.runtime.run_energyplus(self.run_parameters)
        if not self.use_lock:
            self.child_energy.send("Terminated")

    def init(self):
        self.idf.saveas("input.idf")
        self.zone_names = self.get_available_names_under_group("Zone")
        self.get_thermal_names()
        self.warmup_complete = False

    def reset(self):
        self.queue = EventQueue()
        self.historical_values = list()
        self.ignore_list = set()

    def get_current_state_values(self):
        state_values = list(set(self.get_possible_state_values()) - self.ignore_list)
        state_values.sort()
        return state_values

    def select_state_values(self, name=None, index=None):
        current_state = self.get_current_state_values()
        if name is None:
            name = list()
        elif isinstance(name, str):
            name = list(name)
        if index is not None:
            if isinstance(index, int):
                index = [index]
            for i in index:
                if i < len(current_state):
                    name.append(current_state[i])
        self.ignore_list = set(self.get_possible_state_values()) - set(name)

    def add_state_values(self, name):
        if not self.ignore_list:
            return
        if isinstance(name, str):
            name = [name]

        self.ignore_list -= set(name)

    def remove_state_values(self, name):
        if isinstance(name, str):
            name = [name]
        self.ignore_list = self.ignore_list.union(set(name))

    def pop_state_values(self, index):
        current_state = self.get_current_state_values()
        pop_values = list()
        if isinstance(index, int):
            index = [index]
        for i in index:
            if i < len(current_state):
                self.ignore_list.add(current_state[i])
                pop_values.append(current_state[i])

        return pop_values

    def get_possible_state_values(self):
        output = self.get_available_names_under_group("Output:Variable")
        output.sort()
        return output

    def get_possible_actions(self):
        if not os.path.isfile("./result/eplusout.edd"):
            if not self.get_configuration("Output:EnergyManagementSystem"):
                self.add_configuration("Output:EnergyManagementSystem",
                                       values={"Actuator Availability Dictionary Reporting": "Verbose",
                                               "Internal Variable Availability Dictionary Reporting": "Verbose",
                                               "EMS Runtime Language Debug Output Level": "ErrorsOnly"})
            try:
                self.simulate(get_output_files_only=True)
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
