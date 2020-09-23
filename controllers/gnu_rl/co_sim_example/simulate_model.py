import sys, pdb

# from eventqueue import EventQueue
from eppy.modeleditor import IDF
from eppy.bunch_subclass import BadEPFieldError


class Agent:
    def __init__(self):
        pass


class Model:
    model_import_flag = False

    eplus2gnurl = {
        ('Site Outdoor Air Drybulb Temperature', '*'): "Outdoor Temp.",
        ('Site Outdoor Air Relative Humidity', '*'): "Outdoor RH",
        ('Site Wind Speed', '*'): "Wind Speed",
        ('Site Wind Direction', '*'): "Wind Direction",
        ('Site Diffuse Solar Radiation Rate per Area', '*'): "Diff. Solar Rad.",
        ('Site Direct Solar Radiation Rate per Area', '*'): "Direct Solar Rad.",
        ('Building Mean Temperature', '*'): "Indoor Temp.",
        ('Zone Thermostat Heating Setpoint Temperature', 'SPACE1-1'): "Htg SP",
        ('Zone Thermostat Cooling Setpoint Temperature', 'SPACE1-1'): "Clg SP",
        ('Building Mean PPD', '*'): "PPD",
        ('Occupancy Flag', '*'): "Occupancy Flag",
        ('Indoor Air Temperature Setpoint', '*'): "Indoor Temp. Setpoint",
        # ('Building Total Occupants', '*'): "Occupancy Flag",
        ('Heating Coil Electric Power', 'Main Heating Coil 1'): "Coil Power",
        ('Facility Total HVAC Electric Demand Power', '*'): "HVAC Power",
        ('System Node Temperature', 'VAV SYS 1 OUTLET NODE'): "Sys Out Temp.",
        ('System Node Mass Flow Rate', 'VAV SYS 1 OUTLET NODE'): "Sys Out Mdot",
        ('System Node Temperature', 'VAV SYS 1 Inlet NODE'): "Sys In Temp.",
        ('System Node Mass Flow Rate', 'VAV SYS 1 Inlet NODE'): "Sys In Mdot",
        ('System Node Temperature', 'Mixed Air Node 1'): "MA Temp.",
        ('System Node Mass Flow Rate', 'Mixed Air Node 1'): "MA Mdot",
        ('System Node Temperature', 'Outside Air Inlet Node 1'): "OA Temp",
        ('System Node Mass Flow Rate', 'Outside Air Inlet Node 1'): "OA Mdot",
    }

    var_types = {
        'Site Outdoor Air Drybulb Temperature': "Environment",
        'Site Outdoor Air Relative Humidity': "Environment",
        'Site Wind Speed': "Environment",
        'Site Wind Direction': "Environment",
        'Site Diffuse Solar Radiation Rate per Area': "Environment",
        'Site Direct Solar Radiation Rate per Area': "Environment",
        'Building Mean Temperature': "EMS",
        'Facility Total HVAC Electric Demand Power': 'Whole Building',
        'Building Mean PPD': "EMS",
        'Occupancy Flag': "EMS",
        'Indoor Air Temperature Setpoint': "EMS",
    }

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
        self.idf = None
        self.run_parameters = None
#         self.queue = EventQueue()
        self.agent = agent
        self.current_state = None
        self.state_history = []
        self.zone_names = None
        self.thermal_names = None
        self.counter = 0
        self.historical_values = list()
        self.warmup_complete = False

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
        people_zones = self.get_configuration("PEOPLE")
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
        # print('========== STARTING INIT')
        if not self.api.exchange.api_data_fully_ready():
            # print('======= RETURN NOT READY')
            return
        self.warmup_complete = True
        # print('========== READY PRINT', self.api.exchange.list_available_api_data_csv())
        self.save_extended_history()

    def save_extended_history(self):
        state_history = {}
        for entry in self.idf.idfobjects['OUTPUT:VARIABLE']:
            # we only care about the output vars for Gnu-RL
            if (entry['Variable_Name'], entry['Key_Value']) in self.eplus2gnurl.keys():
                var_name = entry['Variable_Name']

                # if the key value is not associated with a zone return None for variable handler
                # key_val = entry['Key_Value'] if entry['Key_Value'] != '*' else None
                if entry['Key_Value'] == '*':
                    key_val = self.var_types[var_name]
                else:
                    key_val = entry['Key_Value']
                handle = self.api.exchange.get_variable_handle(var_name, key_val)
                # name the state value based on Gnu-RL paper
                key = self.eplus2gnurl.get((var_name, entry['Key_Value']))
                state_history[key] = self.api.exchange.get_variable_value(handle)

        # Save the time to the state history
        # set year manual because this gets the year from the epw which is all over the place
        if len(self.state_history) == 0:
            state_history['year'] = 1991  # TODO may want to make a parameter for this
            state_history['month'] = self.api.exchange.month()
            state_history['day'] = self.api.exchange.day_of_month()
            state_history['hour'] = 0
            state_history['minute'] = 0

        else:
            state_history['year'] = 1991  # TODO may want to make a parameter for this
            state_history['month'] = self.api.exchange.month()
            state_history['day'] = self.api.exchange.day_of_month()
            state_history['hour'] = self.api.exchange.hour()
            state_history['minute'] = self.api.exchange.minutes()
        self.state_history.append(state_history)

#     def trigger_events(self):
#         events = self.queue.trigger(self.counter)
#         for key in events["actuator"]:
#             print('============ ACTUATOR')
#             component_type, control_type, actuator_key = key.split("|*|")
#             value = events["actuator"][key][1]
#             handle = self.api.exchange.get_actuator_handle(component_type, control_type, actuator_key)
#             self.api.exchange.set_actuator_value(handle, value)
#         for key in events["global"]:
#             print('============ ACTUATOR')
#             var_name = key
#             value = events["global"][key][1]
#             handle = self.api.exchange.get_global_handle(var_name)
#             self.api.exchange.set_global_value(handle, value)

    def save_current_state(self):
        self.current_state = dict()

        self.current_state["temperature"] = dict()
        for name in self.zone_names:
            handle = self.api.exchange.get_variable_handle("Zone Air Temperature", name)
            self.current_state["temperature"][name] = self.api.exchange.get_variable_value(handle)
        handle = self.api.exchange.get_meter_handle("Electricity:Facility")
        self.current_state["electricity"] = self.api.exchange.get_meter_value(handle)

        if "Zone Thermal Comfort Fanger Model PMV" in self.get_available_names_under_group("OUTPUT:VARIABLE"):
            self.current_state["PMV"] = dict()
            for zone in self.thermal_names:
                handle = self.api.exchange.get_variable_handle("Zone Thermal Comfort Fanger Model PMV", zone)
                self.current_state["PMV"][zone] = self.api.exchange.get_variable_value(handle)

        self.historical_values.append(self.current_state)

    def is_terminal(self):
        pass

    def step(self):
        # TODO api.exchange.warmup_flag seems like it should work here but for some reason it is always true
        if not self.api.exchange.api_data_fully_ready():
            return
        if not self.warmup_complete:
            return

        self.save_current_state()
        # self.trigger_events()
        self.save_extended_history()
        self.counter += 1

        if self.agent:
            # TODO - if task is episodic need a check for terminal state
            self.agent.step(self.current_state)

    def simulate(self):
        from pyenergyplus.api import EnergyPlusAPI

        self.idf.saveas("input.idf")
        self.zone_names = self.get_available_names_under_group("ZONE")
        self.get_thermal_names()
        # for name in self.zone_names:
        #     print(name)
        #     self.current_handle["temperature"][name] = \
        #         self.api.exchange.get_variable_handle("Zone Air Temperature", name)
        # self.current_handle["temperature"] = self.api.exchange.get_variable_handle(
        # "SITE OUTDOOR AIR DRYBULB TEMPERATURE", "ENVIRONMENT")
        # self.current_handle["electricity"] = self.api.exchange.get_meter_handle("Electricity:Facility")
        self.api = EnergyPlusAPI()
        # self.api.runtime.callback_begin_new_environment(self.initialization)
        self.api.runtime.callback_after_new_environment_warmup_complete(self.initialization)
        self.api.runtime.callback_begin_system_timestep_before_predictor(self.step)
        status = self.api.runtime.run_energyplus(self.run_parameters)
        print('Simulator return status: ', status)
        # self.api.runtime.clear_all_states()