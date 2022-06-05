import numpy as np
import json
from random import choice, seed
from datetime import datetime, timedelta
import warnings


class OccupancyGenerator:
    """
    This class use the queueing system to generate the occupancy schedule
    TODO: Add occupancy actions
    """

    def __init__(self,
                 model,
                 num_occupant=10,
                 random_seed=None,
                 transition_matrics=None,
                 office_assignment=None):
        """
        This class contains multiple editable attributes to generate the occupancy schedule. Default setting includes:
        Work shift: 9:00 ~ 17:00, where people start arriving/leaving 30 minutes earily.
        Group meeting: 16:00, once per day, last average 15 minutes.
        Lunch time: 12:00 ~ 13:00.
        Call for absence probability: 1%.
        Chat with colleague: average 30 minutes each.
        Customer service time: average 30 minutes each.
        Average number of guests per day: 3.

        :parameter model: The ``COBS.Model`` class object as the target building model.

        :parameter num_occupant: The number of long-term occupants belongs to the model.
        :parameter random_seed: The seed for numpy and random module. None means no seed specified.
        :parameter transition_matrics: A list/tuple of numpy.ndarray, or a single numpy.ndarray, or None.
        Each numpy.ndarray must be in the shape of (len(self.possible_locations), len(self.possible_locations)).
        The first len(self.possible_locations) - 1 row and column represents the transition rate between zones that are in the order of self.possible_locations.
        The last row and column represents the transition rate of the office to other zones (will overwrite previous transition rate).
        Transition rate in the unit of seconds.
        None means the occupant always stay in the office.
        :parameter office_assignment: A list/tuple of zone names or None.
        Each entry indicates the assigned office for the corresponding occupant. If length < num_occupant, other occupants will be assigned randomly.
        Each entry must be a valid zone name included in the building IDF file.
        """
        if random_seed is not None:
            seed(random_seed)
            np.random.seed(random_seed)
        self.work_start_time = 9 * 60 * 60  # Work start from 9:00. unit: second
        self.work_end_time = 17 * 60 * 60  # Work end at 17:00. unit: second
        self.meeting_time = 16 * 60 * 60  # Daily progress report at 16:00, in meeting room
        self.meeting_length_avg = 15 * 60  # Daily progress report average length 15 min
        self.meeting_length_std = 1 * 60  # Daily progress report std.dev 1 min
        self.max_earliness = 30 * 60  # Tend to come 8:30, average arrive at 9:00. Leave is similar. Exponential distribution
        self.call_for_absence_prob = 0.01  # Possibility of not come to the office
        self.lunch_break_start = 12 * 60 * 60  # Lunch serve start time 12:00. unit: second
        self.lunch_break_end = 13 * 60 * 60  # Lunch serve end time 13:00. unit: second
        self.eat_time_a = 10  # average time for each person to eat lunch. Beta distribution
        self.eat_time_b = self.lunch_break_end - self.lunch_break_start  # average time for each person to eat lunch. Beta distribution
        self.cut_off_time = 14 * 60 * 60  # After this time, the person won't come to work
        self.day_cut_off = 24 * 60 * 60
        self.start_synthetic_data = datetime(2020, 3, 25)  # start date
        self.end_synthetic_data = datetime(2020, 3, 27)  # end date
        self.report_interval = timedelta(seconds=60)  # Time interval between two consecutive package
        self.guest_lambda = 3  # Poisson arrival for unknown customers. unit: person per day
        self.visit_colleague_lambda = 3  # How many times a worker goes to a colleague's office
        self.average_stay_in_colleague_office = 30 * 60
        self.std_stay_in_colleague_office = 4 * 60
        self.average_stay_customer = 30 * 60
        self.std_stay_customer = 5 * 60
        # TODO: Add zone trespass time
        self.model = model
        self.possible_locations = self.model.get_available_names_under_group("Zone")
        self.work_zones = self.possible_locations[:]
        self.zone_link = model.get_link_zones()
        self.meeting_room = choice(self.possible_locations)
        self.lunch_room = choice(self.possible_locations)
        self.entry_zone = choice(list(self.zone_link["Outdoor"]))
        self.possible_locations.insert(0, "Outdoor")
        self.possible_locations.append("busy")
        self.weekdays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        self.office_assignment = list()

        self.work_zones.remove(self.lunch_room)
        if self.meeting_room != self.lunch_room:
            self.work_zones.remove(self.meeting_room)

        if office_assignment is not None:
            for zone_name in office_assignment:
                if zone_name == self.meeting_room or self.lunch_room:
                    warnings.warn(f"Assigned office zone {zone_name} is a meeting room or lunch room.")
                if zone_name in self.possible_locations:
                    self.office_assignment.append(zone_name)
                else:
                    raise ValueError(f"Assigned office zone {zone_name} does not exist.")

        while len(self.office_assignment) < num_occupant:
            self.office_assignment.append(choice(self.work_zones))

        if isinstance(transition_matrics, (tuple, list)):
            if len(transition_matrics) != num_occupant:
                raise ValueError(f"Length of the transition_matrics must be num_occupant {num_occupant}.")
            self.worker_assign = [Person(self,
                                         office=self.office_assignment[i],
                                         transition_rate_matrix=transition_matrics[i]) for i in range(num_occupant)]
        elif isinstance(transition_matrics, np.ndarray):
            self.worker_assign = [Person(self,
                                         office=self.office_assignment[i],
                                         transition_rate_matrix=transition_matrics.copy()) for i in range(num_occupant)]
        elif transition_matrics is None:
            self.worker_assign = [Person(self,
                                         office=self.office_assignment[i]) for i in range(num_occupant)]
        else:
            raise ValueError("transition_matrics must be a list/tuple of numpy.ndarray, single numpy.ndarray, or None.")

        # value = (np.random.beta(eat_time_a, eat_time_b, 10000) + 0.1) * 100

    def set_transition_matrics(self, transition_matrics):
        """
        Set the transition matrics to each corresponding person.

        :param transition_matrics: A list of matrics or one matrix
        """
        if isinstance(transition_matrics, (tuple, list)):
            if len(transition_matrics) != len(self.worker_assign):
                raise ValueError(f"Length of the transition_matrics must be num_occupant {len(self.worker_assign)}.")
            for i, q in enumerate(transition_matrics):
                self.worker_assign[i].set_transition_matrix(q)
        elif isinstance(transition_matrics, np.ndarray):
            if transition_matrics.ndim == 3:
                if transition_matrics.shape[0] != len(self.worker_assign):
                    raise ValueError(f"For concatenated numpy array, the shape of the transition_matrics must be"
                                     f" ({len(self.worker_assign)}, "
                                     f"{len(self.possible_locations)}, {len(self.possible_locations)}).")
                for i in range(transition_matrics.shape[0]):
                    self.worker_assign[i].set_transition_matrix(transition_matrics[i, :, :])
            else:
                for worker in self.worker_assign:
                    worker.set_transition_matrix(transition_matrics.copy())

    def get_path(self, start, end):
        """
        Use BFS to find the shortest path between two zones.

        :parameter start: The entry of the start zone.

        :parameter end: The entry of the target zone.

        :return: A list of zone names that the occupant need to cross.
        """
        queue = [(start, [start])]
        visited = set()

        while queue:
            vertex, path = queue.pop(0)
            visited.add(vertex)
            for node in self.zone_link[vertex]:
                if node == end:
                    return path + [end]
                else:
                    if node not in visited:
                        visited.add(node)
                        queue.append((node, path + [node]))
        return [start]

    def generate_all_people_daily_movement(self, use_scheduled_events=True):
        """
        Generate a list of ``Person`` objects and simulate the movement for each person.

        :return: list of ``Person`` objects.
        """
        available_worker = list()
        for i, worker in enumerate(self.worker_assign):
            if worker.decide_come():
                available_worker.append(i)

        # print(available_worker)

        guests = np.random.poisson(self.guest_lambda) if use_scheduled_events else 0
        guest_assign = np.random.choice(available_worker, size=guests)
        all_people = list()
        guest_counter = 0

        for i in available_worker:
            worker = self.worker_assign[i]
            all_people.append(worker)
            guest_list = np.random.randint(1, 4, size=np.sum(guest_assign == i))
            appointments = worker.generate_daily_route(guest_list, use_scheduled_events)
            for j, appointment in enumerate(appointments):
                for _ in range(guest_list[j]):
                    new_guest = Person(self)
                    guest_counter += 1
                    new_guest.customer_come(*appointment)
                    all_people.append(new_guest)

        return all_people

    def generate_daily_schedule(self, add_to_model=True, overwrite_dict=None, use_scheduled_events=True):
        """
        Generate a numpy matrix contains the locations of all occupants in the day and add tp the model.

        :parameter add_to_model: Default is True. If False, then only generate the schedule in numpy and IDF format but not save to the model automatically.

        :parameter overwrite_dict: Default is None. If set to a dict with {zone_name: old_people_object_name}, it will overwrite existing People instead of creating a new one

        :parameter use_scheduled_events: Default is True. Determines if the lunch and group meeting event will be simulated

        :return: Three objects, (IDF format schedule, numpy format schedule, list of all accessble locations in the building).
        """
        all_zones = self.model.get_available_names_under_group("Zone")
        valid_zones = list()
        for zone in all_zones:
            if zone in self.possible_locations:
                valid_zones.append(zone)
        all_people = self.generate_all_people_daily_movement(use_scheduled_events)
        locations = list()
        for person in all_people:
            locations.append(person.position.copy())
            if person.office is not None:
                locations[-1][locations[-1] == self.possible_locations.index('busy')] = \
                    self.possible_locations.index(person.office)

        location_matrix = np.vstack(locations)
        all_commands = list()

        if add_to_model:
            act, work, cloth, air = self.occupancy_prep()
            self.model.add_configuration("Output:Variable", values={"Variable Name": "Zone People Occupant Count",
                                                                    "Reporting_Frequency": "timestep"})
            self.model.add_configuration("Output:Variable",
                                         values={"Variable Name": "Zone Thermal Comfort Fanger Model PMV",
                                                 "Reporting_Frequency": "timestep"})

        zone_occupancy = np.zeros((len(self.possible_locations), 24 * 60))

        for zone in valid_zones:
            i = self.possible_locations.index(zone)
            occupancy = np.sum(location_matrix == i, axis=0)

            result_command = {"Name": f"Generated_Schedule_Zone_{zone}",
                              "Schedule Type Limits Name": "Any Number",
                              "Field 1": "Through: 12/31",
                              "Field 2": "For: Weekdays"}

            counter = 3
            for t in range(1, 24 * 60 + 1):
                zone_occupancy[i, t - 1] = occupancy[t * 60 - 1]
                if t != 24 * 60 and occupancy[(t + 1) * 60 - 1] == occupancy[t * 60 - 1]:
                    continue
                hour = t // 60
                min = t % 60
                result_command[f"Field {counter}"] = f"Until {hour:02d}:{min:02d}"
                result_command[f"Field {counter + 1}"] = f"{occupancy[t * 60 - 1]}"
                counter += 2

            all_commands.append(result_command)
            if add_to_model:
                self.model.add_configuration("Schedule:Compact", values=result_command)
                if overwrite_dict is not None and zone in overwrite_dict:
                    self.model.edit_configuration("People",
                                                  {"Name": overwrite_dict[zone]},
                                                  {"Number of People": 1,
                                                   "Number of People Schedule Name": f"Generated_Schedule_Zone_{zone}"})
                else:
                    people_values = {"Name": f"Test_Zone_{zone}",
                                     "Zone or ZoneList Name": zone,
                                     "Number of People Schedule Name": f"Generated_Schedule_Zone_{zone}",
                                     "Number of People": 1,
                                     "Activity Level Schedule Name": act,
                                     "Work Efficiency Schedule Name": work,
                                     "Clothing Insulation Schedule Name": cloth,
                                     "Air Velocity Schedule Name": air,
                                     "Thermal Comfort Model 1 Type": "Fanger"}
                    self.model.add_configuration("People", values=people_values)

        return all_commands, location_matrix, zone_occupancy, self.possible_locations

    def one_day_numpy_to_schedule(self, array, name):
        result_command = {"Name": f"{name}",
                          "Schedule Type Limits Name": "Any Number"}

        counter = 1
        for t in range(1, 24 * 60 + 1):
            if t < 24 * 60 and array[t] == array[t - 1]:
                continue
            hour = t // 60
            minute = t % 60
            result_command[f"Time {counter}"] = f"Until {hour:02d}:{minute:02d}"
            result_command[f"Value Until Time {counter}"] = f"{int(array[t - 1])}"
            counter += 1

        return self.model.add_configuration("Schedule:Day:Interval", values=result_command)

    def daily_to_week(self, daily_name_list, name, start_day):
        result_command = {"Name": f"{name}"}

        for i, daily_name in enumerate(daily_name_list):
            result_command[f"{self.weekdays[(start_day + i) % len(self.weekdays)]} Schedule:Day Name"] = daily_name

        result_command["Holiday Schedule:Day Name"] = result_command["Sunday Schedule:Day Name"]
        result_command["SummerDesignDay Schedule:Day Name"] = result_command["Sunday Schedule:Day Name"]
        result_command["WinterDesignDay Schedule:Day Name"] = result_command["Sunday Schedule:Day Name"]
        result_command["CustomDay1 Schedule:Day Name"] = result_command["Sunday Schedule:Day Name"]
        result_command["CustomDay2 Schedule:Day Name"] = result_command["Sunday Schedule:Day Name"]

        return self.model.add_configuration("Schedule:Week:Daily", values=result_command)

    def weeks_to_year(self, week_name_list, name):
        result_command = {"Name": f"{name}",
                          "Schedule Type Limits Name": "Any Number"}

        start = datetime(1995 + self.model.leap_weather, 1, 1)
        start_next = datetime(1995 + self.model.leap_weather, 1, 1)
        counter = 1
        for t in range(1, 54):
            start_next = start_next + timedelta(days=7)
            if t < 53 and week_name_list[t - 1] == week_name_list[t]:
                continue
            end = start_next - timedelta(days=1)
            result_command[f"Schedule:Week Name {counter}"] = week_name_list[t - 1]
            result_command[f"Start Month {counter}"] = start.month
            result_command[f"Start Day {counter}"] = start.day
            result_command[f"End Month {counter}"] = end.month
            result_command[f"End Day {counter}"] = end.day
            start = start_next
            counter += 1

        result_command[f"End Month {counter - 1}"] = 12
        result_command[f"End Day {counter - 1}"] = 31

        return self.model.add_configuration("Schedule:Year", values=result_command)

    def occupancy_prep(self):
        activity_values = {"Name": "Test_Activity_Schedule",
                           "Schedule Type Limits Name": "Any Number",
                           "Field 1": "Through:12/31",
                           "Field 2": "For: Alldays",
                           "Field 3": "Until 24:00",
                           "Field 4": "200"}

        work_efficiency = {"Name": "Test_Work_Schedule",
                           "Schedule Type Limits Name": "Fraction",
                           "Field 1": "Through:12/31",
                           "Field 2": "For: Alldays",
                           "Field 3": "Until 24:00",
                           "Field 4": "0.1"}

        cloth_schedule = {"Name": "Test_Cloth_Schedule",
                          "Schedule Type Limits Name": "Fraction",
                          "Field 1": "Through:12/31",
                          "Field 2": "For: Alldays",
                          "Field 3": "Until 24:00",
                          "Field 4": "0.9"}

        air_velocity = {"Name": "Test_Air_Velocity",
                        "Schedule Type Limits Name": "Fraction",
                        "Field 1": "Through:12/31",
                        "Field 2": "For: Alldays",
                        "Field 3": "Until 24:00",
                        "Field 4": "0.25"}

        returns = [activity_values["Name"], work_efficiency["Name"], cloth_schedule["Name"], air_velocity["Name"]]

        if len(self.model.get_configuration("People")) == 0:

            self.model.add_configuration("Schedule:Compact", values=activity_values)
            self.model.add_configuration("Schedule:Compact", values=work_efficiency)
            self.model.add_configuration("Schedule:Compact", values=cloth_schedule)
            self.model.add_configuration("Schedule:Compact", values=air_velocity)

        else:
            prev = self.model.get_configuration("People")[0]

            for i, name, var in ((0, "Activity Level Schedule Name", activity_values),
                                 (1, "Work Efficiency Schedule Name", work_efficiency),
                                 (2, "Clothing Insulation Schedule Name", cloth_schedule),
                                 (3, "Air Velocity Schedule Name", air_velocity)):
                if name not in prev:
                    self.model.add_configuration("Schedule:Compact", values=var)
                else:
                    returns[i] = prev[name]

            return returns

    def generate_schedule_using_numpy(self, occupancy, room_name=None, start_day=0, overwrite_dict=None):
        """
        Generate the occupancy pattern based on a given numpy ndarray, and add it to the model.

        :parameter occupancy: The numpy array with shape of (365, number_of_room, 24 * 60),
        where the first dimension indicates the 365 days on a year, the second dimension indicates the occupancy for
        each room, and the third dimension indicates the minute in a day. The value of this ndarray should be the
        number of occupants in the room at a specific time on a specific day. If the second dimension < actual number
        of rooms, the rest rooms are considered unoccupied all the time.

        :parameter room_name: an iterable object contains the name of rooms in the order they stored in the occupancy
        ndarray's second dimension. If room_name is not provided, then the default order will be used.

        :parameter start_day: Specify the start day of the week. 0 means Sunday, and 6 means Saturday.

        :parameter overwrite_dict: Default is None. If set to a dict with {zone_name: old_people_object_name},
        it will overwrite existing People instead of creating a new one
        """
        if not isinstance(occupancy, np.ndarray) or \
                occupancy.ndim != 3 or \
                occupancy.shape[0] != 365 + self.model.leap_weather or \
                occupancy.shape[2] != 24 * 60:
            raise ValueError(f"Wrong format of the occupancy numpy array. "
                             f"The shape must be ({365 + self.model.leap_weather}, n, 24 * 60)")
        if room_name is None:
            room_name = self.model.get_available_names_under_group("Zone")

        occupancy = occupancy.astype(int)
        days, rooms, _ = occupancy.shape

        name = self.model.get_configuration("RunPeriod")[0].Name
        self.model.edit_configuration("RunPeriod",
                                      {"Name": name},
                                      {"Day of Week for Start Day": self.weekdays[start_day]})

        occupancy, corres_id = np.unique(occupancy.reshape(-1, 24 * 60), axis=0, return_inverse=True)
        for i, row in enumerate(occupancy):
            self.one_day_numpy_to_schedule(row, name=f"Day Type {i}")

        occupancy, corres_id = np.unique(np.concatenate((corres_id.reshape(days, -1),
                                                         np.zeros((7 - days % 7, rooms))), axis=0).T.reshape(-1, 7),
                                         axis=0, return_inverse=True)

        for i, row in enumerate(occupancy.astype(int)):
            self.daily_to_week(map(lambda x: f"Day Type {x}", row), name=f"Week Type {i}", start_day=start_day)

        for i, row in enumerate(corres_id.reshape(rooms, -1).astype(int)):
            if i == len(room_name):
                break
            self.weeks_to_year(list(map(lambda x: f"Week Type {x}", row)), name=f"Year For {room_name[i]}")
            if overwrite_dict is not None and room_name[i] in overwrite_dict:
                self.model.edit_configuration("People",
                                              {"Name": overwrite_dict[room_name[i]]},
                                              {"Number of People": 1,
                                               "Number of People Schedule Name": f"Year For {room_name[i]}"})
            else:
                act, work, cloth, air = self.occupancy_prep()
                people_values = {"Name": f"Test_Zone_{room_name[i]}",
                                 "Zone or ZoneList Name": room_name[i],
                                 "Number of People Schedule Name": f"Year For {room_name[i]}",
                                 "Number of People": 1,
                                 "Activity Level Schedule Name": act,
                                 "Work Efficiency Schedule Name": work,
                                 "Clothing Insulation Schedule Name": cloth,
                                 "Air Velocity Schedule Name": air,
                                 "Thermal Comfort Model 1 Type": "Fanger"}
                self.model.add_configuration("People", values=people_values)

    def save_light_config(self, output_name=None):
        if self.light_config is None:
            self.initialize_light_config()
        if output_name is None:
            output_name = "light_config.json"
        with open(output_name, 'w') as output_file:
            json.dump(self.light_config, output_file)

    def initialize_light_config(self):
        zone_lights = self.model.get_lights()
        self.light_config = dict()
        print(self.model.get_windows())
        for zone in zone_lights:
            self.light_config[zone] = list()
            for light in zone_lights[zone]:
                self.light_config[zone].append({"name": light,
                                                "probability": 1,
                                                "condition": {zone_name: {"occupancy > 0": 1,
                                                                          "occupancy == 0": 1}
                                                              for zone_name in self.possible_locations}})

    def generate_light(self, input_name=None):
        pass


class Person:
    """
    This class contains the detail location of a single occupant.
    """

    def __init__(self, generator, office=None, transition_rate_matrix=None):
        """
        Each long-term occupant will have an office, and he tend to stay in office more than other places.

        :parameter generator: The OccupancyGenerator which provides the settings.

        :parameter office: The designated office for long-term occupants.

        :parameter transition_rate_matrix: The transition rate matrix for the current occupants (if None, assume the occupant tends to stay in the office).
        """
        self.office = office
        self.position = np.zeros(generator.day_cut_off)
        self.source = generator
        self.start_time = 0
        self.end_time = 0
        self.transition_matrix = None
        if transition_rate_matrix is not None:
            self.set_transition_matrix(transition_rate_matrix)

    def set_transition_matrix(self, transition_rate_matrix):
        """
        Define the transition matrix for the current person

        :param transition_rate_matrix: The transition matrix - a numpy array with shape
        (num_possible_zone + 2, num_possible_zone + 2). The order is [Outdoor, each zone, office]
        """
        if not isinstance(transition_rate_matrix, np.ndarray):
            raise ValueError(f"The provided transition matrix be a numpy.ndarray")
        if len(self.source.possible_locations) != transition_rate_matrix.shape[0] or \
                len(self.source.possible_locations) != transition_rate_matrix.shape[1]:
            raise ValueError(f"The provided transition matrix must in shape "
                             f"({len(self.source.possible_locations)}, {len(self.source.possible_locations)})")

        office_idx = self.source.possible_locations.index(self.office)
        self.transition_matrix = transition_rate_matrix[:-1, :-1]
        if np.sum(transition_rate_matrix[-1, :]) + np.sum(transition_rate_matrix[-1, :]) == 0:
            return
        self.transition_matrix[office_idx, :office_idx] = transition_rate_matrix[-1, :office_idx]
        self.transition_matrix[office_idx, office_idx:] = transition_rate_matrix[-1, office_idx:-1]
        self.transition_matrix[:office_idx, office_idx] = transition_rate_matrix[:office_idx, -1]
        self.transition_matrix[office_idx:, office_idx] = transition_rate_matrix[office_idx:-1, -1]
        for i in range(self.transition_matrix.shape[0]):
            self.transition_matrix[i, i] = 0
            self.transition_matrix[i, i] = np.sum(self.transition_matrix[i, :])

    def customer_come(self, start_time, end_time, dest):
        """
        Simulate the event of customers coming for the current occupant.

        :parameter start_time: The scheduled appointment start time (not the real start time).

        :parameter end_time: The scheduled appointment end time (not the real end time).

        :parameter dest: The appointment location (zone entry).

        :return: None
        """
        pass_zones = self.source.get_path(self.source.entry_zone, dest)

        zone_move_timer = list()
        # real_start_time = start_time - int(np.random.exponential(5 * 60))  # Come eariler than expected
        zone_move_timer.append(start_time - int(np.random.exponential(5 * 60)))  # Come eariler than expected
        # decide the time takes from Room_1_1_150 door to the meeting room
        # TODO: Trespass time
        temp_timer = start_time
        for _ in pass_zones[1:]:
            temp_timer = temp_timer - 3 + get_white_bias(1)
            zone_move_timer.insert(1, temp_timer)

        temp_timer = end_time
        for _ in pass_zones:
            zone_move_timer.append(temp_timer)
            temp_timer = temp_timer + 3 + get_white_bias(1)

        # Apply to the daily route
        for i in range(len(zone_move_timer) - 1):
            self.position[zone_move_timer[i]:zone_move_timer[i + 1]] = \
                self.source.possible_locations.index(pass_zones[len(pass_zones) - abs(i - len(pass_zones) + 1) - 1])

    def decide_come(self):
        """
        Each person need to decide if he/she will come to work today, when exactly they come, and when exactly
        they leave. We assume people start to come at 8:30 am and leave at 5 pm, with a poisson arrival lambda = 30 min.
        Notice that we simulate this as poisson arrival, which means two arrivals are not independent.

        :return: True if come to work, False otherwise
        """
        self.position = np.zeros(self.source.day_cut_off)
        # Decide absence
        if np.random.random() < self.source.call_for_absence_prob:
            return False
        else:
            # Decide when come to office
            arrival_time = (self.source.work_start_time - self.source.max_earliness) + \
                           int(np.random.exponential(self.source.max_earliness))
            if arrival_time > self.source.cut_off_time:
                return False
            else:
                # Decide when go back home
                leave_time = self.source.work_end_time + int(np.random.exponential(self.source.max_earliness))
                if leave_time >= self.source.day_cut_off:
                    leave_time = self.source.day_cut_off - 1

                self.start_time = arrival_time
                self.end_time = leave_time

                pass_zones = self.source.get_path(self.source.entry_zone, self.office)

                zone_move_timer = list()
                # TODO: Trespass time
                temp_timer = arrival_time
                for _ in pass_zones:
                    zone_move_timer.append(temp_timer)
                    temp_timer = temp_timer + 3 + get_white_bias(1)

                temp_timer = leave_time
                for _ in pass_zones:
                    zone_move_timer.insert(len(pass_zones), temp_timer)
                    temp_timer = temp_timer - 3 + get_white_bias(1)

                # Apply to the daily route
                for i in range(len(zone_move_timer) - 1):
                    self.position[zone_move_timer[i]:zone_move_timer[i + 1]] = \
                        self.source.possible_locations.index(
                            pass_zones[len(pass_zones) - abs(i - len(pass_zones) + 1) - 1])

                return True

    def generate_lunch(self):
        """
        Generate the time that current occupant go to the cafeteria and take the lunch.

        :return: None
        """
        # Usually go for lunch immediately, with average delay of 5 minute
        lunch_delay = int(np.random.exponential(5 * 60))
        lunch_delay = max(lunch_delay, 20 * 60)

        pass_zones = self.source.get_path(self.office, self.source.lunch_room)
        pass_zones.pop(0)
        zone_move_timer = [self.source.lunch_break_start]
        # TODO: Trespass time
        temp_timer = self.source.lunch_break_start + lunch_delay
        for _ in pass_zones[:-1]:
            temp_timer = temp_timer + 3 + get_white_bias(1)
            zone_move_timer.append(temp_timer)

        zone_move_timer.append(temp_timer +
                               int((np.random.beta(self.source.eat_time_a, self.source.eat_time_b) + 0.1) * 6000))

        temp_timer = zone_move_timer[-1]
        for _ in pass_zones[:-1]:
            temp_timer = temp_timer + 3 + get_white_bias(1)
            zone_move_timer.append(temp_timer)

        # Apply to the daily route
        for i in range(len(zone_move_timer) - 1):
            self.position[zone_move_timer[i]:zone_move_timer[i + 1]] = \
                self.source.possible_locations.index(
                    pass_zones[len(pass_zones) - abs(i - len(pass_zones) + 1) - 1])

    def generate_daily_meeting(self):
        """
        Generate the time that current occupant go to the daily meeting.

        :return: None
        """
        # Arrive maximum 3 min early, 2 min late
        meeting_attend = int(np.random.exponential(3 * 60))
        meeting_attend = self.source.meeting_time - max(meeting_attend, 5 * 60)

        pass_zones = self.source.get_path(self.office, self.source.meeting_room)
        pass_zones.pop(0)
        zone_move_timer = [meeting_attend]
        # TODO: Trespass time
        temp_timer = meeting_attend
        for _ in pass_zones[:-1]:
            temp_timer = temp_timer - 3 + get_white_bias(1)
            zone_move_timer.insert(0, temp_timer)

        zone_move_timer.append(self.source.meeting_time +
                               int(np.random.normal(self.source.meeting_length_avg, self.source.meeting_length_std)))

        temp_timer = zone_move_timer[-1]
        for _ in pass_zones[:-1]:
            temp_timer = temp_timer + 3 + get_white_bias(1)
            zone_move_timer.append(temp_timer)

        # Apply to the daily route
        for i in range(len(zone_move_timer) - 1):
            self.position[zone_move_timer[i]:zone_move_timer[i + 1]] = \
                self.source.possible_locations.index(
                    pass_zones[len(pass_zones) - abs(i - len(pass_zones) + 1) - 1])

    def check_in_office(self, start, end):
        """
        Determine if the occupant is in his/her office or not during a given period of time.

        :parameter start: The start time.

        :parameter end: The end time.

        :return: Return True if the occupant is in his/her office between given time, and False otherwise.
        """
        return np.sum(self.position[start:end] == self.source.possible_locations.index(self.office)) == (end - start)

    def get_in_office_range(self):
        """
        Find all times that the occupant is in his/her office.
        :return: list of timeslots that the occupant is in the office
        """
        in_office = np.concatenate(([0],
                                    np.equal(self.position,
                                             self.source.possible_locations.index(self.office)).view(np.int8),
                                    [0]))
        absdiff = np.abs(np.diff(in_office))
        # Runs start and end where absdiff is 1.
        ranges = np.where(absdiff == 1)[0].reshape(-1, 2)
        return ranges

    def handle_customer(self, num_customer):
        """
        Set up an appointment for occupant with some new customers.

        :parameter num_customer: Number of customers in total today will come.

        :return: tuple of (appointment start time, appointment end time, appointment location).
        """
        # Set-up meeting time
        in_office_range = self.get_in_office_range()
        visit_length = int(np.random.normal(self.source.average_stay_customer, self.source.std_stay_customer))
        in_office_duration = in_office_range[:, 1] - in_office_range[:, 0]
        in_office_idx = np.nonzero(in_office_duration > visit_length)[0]
        if len(in_office_idx) == 0:
            visit_length = np.max(in_office_duration)
            in_office_idx = np.nonzero(in_office_duration == visit_length)[0]
        idx = np.random.choice(in_office_idx)
        start_time = np.random.randint(in_office_range[idx, 0], in_office_range[idx, 1] - visit_length + 1)
        end_time = start_time + visit_length

        in_room = start_time + 10 + get_white_bias(1)
        out_room = end_time - 10 + get_white_bias(1)

        # Decide meeting location
        if num_customer > 1:
            # Go meet in meeting room
            room_name = self.source.meeting_room
            self.position[in_room:out_room] = self.source.possible_locations.index(self.source.meeting_room)
        else:
            self.position[in_room:out_room] = self.source.possible_locations.index("busy")
            room_name = self.office

        return in_room, out_room, room_name

    def generate_go_other_office(self):
        """
        Generate the event of visiting colleagues' office for random talk. Only possible if the colleague is in the office.

        :return: None.
        """
        for _ in range(np.random.poisson(self.source.visit_colleague_lambda)):
            # Find available time for current person to meet some colleague
            in_office_range = self.get_in_office_range()
            visit_length = int(np.random.normal(self.source.average_stay_in_colleague_office,
                                                self.source.std_stay_in_colleague_office))
            in_office_idx = np.nonzero((in_office_range[:, 1] - in_office_range[:, 0]) > visit_length)[0]
            if len(in_office_idx) == 0:
                continue
            idx = np.random.choice(in_office_idx)
            start_time = np.random.randint(in_office_range[idx, 0], in_office_range[idx, 1] - visit_length + 1)
            end_time = start_time + visit_length

            # Find available colleague
            for coworker in self.source.worker_assign:
                if coworker.check_in_office(start_time, end_time):
                    # Go meet the colleague
                    in_colleague = start_time + 10 + get_white_bias(1)
                    out_colleague = end_time - 10 + get_white_bias(1)

                    self.position[in_colleague:out_colleague] = self.source.possible_locations.index(coworker.office)
                    coworker.position[in_colleague:out_colleague] = self.source.possible_locations.index("busy")
                    break

    def generate_daily_route(self, customer_list, use_scheduled_events=True):
        """
        Generate the whole day locations for the occupant.

        :parameter customer_list: List of Person that will visit the occupant today.

        :return: List of appointment times.
        """
        if self.transition_matrix is not None:
            self.generate_base_positions()

        time_list = list()
        if use_scheduled_events:
            self.generate_lunch()
            self.generate_daily_meeting()
            if self.transition_matrix is not None:
                for num_customer in customer_list:
                    time_list.append(self.handle_customer(num_customer))
                self.generate_go_other_office()
        return time_list

    def generate_base_positions(self, method="DTMC"):
        """
        Generate the positions based on the transition rate matrix
        :return: None.
        """
        next_positions = self.source.possible_locations[:-1]

        current_time = self.start_time
        current_location = self.source.possible_locations.index("Outdoor")
        initial = True
        while current_time < self.end_time:
            if method == "Competing Clocks":
                timers = np.random.exponential(1 / self.transition_matrix[current_location, :])
                next_location = timers.argmin()
                if next_location == current_location:
                    timers[next_location] += np.max(timers)
                    next_location = timers.argmin()
                stay_time = int(np.round(timers[next_location]))

            elif method == "DTMC":
                stay_time = int(np.round(np.random.exponential(1 / self.transition_matrix[current_location,
                                                                                          current_location])))
                p = np.random.exponential(1 / (self.transition_matrix[current_location, :] /
                                               self.transition_matrix[current_location, current_location]))
                p[current_location] = 0
                next_location = np.random.choice(range(len(next_positions)), p=p / np.sum(p))

            else:
                raise ValueError("Unknown transition generation method")

            if initial:
                current_location = next_location
                initial = False

            else:
                if current_time + stay_time > self.end_time:
                    current_time = self.end_time
                    pass_zones = self.source.get_path(next_positions[current_location], "Outdoor")

                    for i in range(len(pass_zones) - 1, 0, -1):
                        tres_time = 3 + get_white_bias(1)
                        self.position[current_time - tres_time:current_time] = next_positions.index(pass_zones[i])
                        current_time -= tres_time
                    current_time = self.end_time
                else:
                    self.position[current_time + 1:current_time + stay_time] = current_location
                    current_time += stay_time
                    # TODO: Trespass time
                    pass_zones = self.source.get_path(next_positions[current_location], next_positions[next_location])
                    for i in range(1, len(pass_zones)):
                        tres_time = 3 + get_white_bias(1)
                        self.position[current_time + 1:current_time + tres_time] = next_positions.index(pass_zones[i])
                        current_time += tres_time

                    current_location = next_location

    def get_position(self, sec):
        """
        Get the location of the occupant at the given time

        :parameter sec: The time that need to check.

        :return: The zone entry of the location at the given time.
        """
        if self.position[sec] == self.source.possible_locations.index("busy"):
            return self.office
        return self.source.possible_locations[int(self.position[sec])]

    def get_trigger(self):
        pass


def get_white_bias(second):
    """
    Generate a bias.

    :parameter second: Value range.

    :return: Bias.
    """
    return np.random.randint(second * 2 + 1) - second


if __name__ == '__main__':
    pass
