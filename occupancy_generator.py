import numpy as np
from random import choice
from datetime import datetime, timedelta


class OccupancyGenerator:

    def __init__(self,
                 model,
                 num_worker=10):
        self.start_work = 9 * 60 * 60  # Work start from 9:00. unit: second
        self.end_work = 17 * 60 * 60  # Work end at 17:00. unit: second
        self.daily_report = 16 * 60 * 60  # Daily progress report at 16:00, in meeting room
        self.daily_report_mean = 15 * 60  # Daily progress report average length 15 min
        self.daily_report_std = 1 * 60  # Daily progress report std.dev 1 min
        self.come_leave_flex_coef = 30 * 60  # Tend to come 8:30, average arrive at 9:00. Leave is similar. Exponential distribution
        self.call_for_absence = 0.01  # Possibility of not come to the office
        self.lunch_start_time = 12 * 60 * 60  # Lunch serve start time 12:00. unit: second
        self.lunch_end_time = 13 * 60 * 60  # Lunch serve end time 13:00. unit: second
        self.eat_time_a = 10  # average time for each person to eat lunch. Beta distribution
        self.eat_time_b = 50  # average time for each person to eat lunch. Beta distribution
        self.cut_off_time = 14 * 60 * 60  # After this time, the person won't come to work
        self.day_cut_off = 24 * 60 * 60
        self.start_synthetic_data = datetime(2020, 3, 25)  # start date
        self.end_synthetic_data = datetime(2020, 3, 27)  # end date
        self.report_interval = timedelta(seconds=60)  # Time interval between two consecutive package
        self.guest_lambda = 3  # Poisson arrival for unknown customers. unit: person per day
        self.visit_colleague = 3  # How many times a worker goes to a colleague's office
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

        self.work_zones.remove(self.lunch_room)
        if self.meeting_room != self.lunch_room:
            self.work_zones.remove(self.meeting_room)

        self.worker_assign = [Person(self, office=choice(self.work_zones)) for _ in range(num_worker)]

        # value = (np.random.beta(eat_time_a, eat_time_b, 10000) + 0.1) * 100

    def get_path(self, start, end):
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

    def generate_daily_data(self):
        available_worker = list()
        for i, worker in enumerate(self.worker_assign):
            if worker.decide_come():
                available_worker.append(i)

        # print(available_worker)

        guests = np.random.poisson(self.guest_lambda)
        guest_assign = np.random.choice(available_worker, size=guests)
        all_people = list()
        guest_counter = 0

        for i in available_worker:
            worker = self.worker_assign[i]
            all_people.append(worker)
            guest_list = np.random.randint(1, 4, size=np.sum(guest_assign == i))
            appointments = worker.generate_daily_route(guest_list)
            for j, appointment in enumerate(appointments):
                for _ in range(guest_list[j]):
                    new_guest = Person(self)
                    guest_counter += 1
                    new_guest.customer_come(*appointment)
                    all_people.append(new_guest)

        return all_people

    def generate_daily_schedule(self, add_to_model=True):
        all_zones = self.model.get_available_names_under_group("Zone")
        valid_zones = list()
        for zone in all_zones:
            if zone in self.possible_locations:
                valid_zones.append(zone)
        all_people = self.generate_daily_data()
        locations = list()
        for person in all_people:
            locations.append(person.position.copy())
            if person.office is not None:
                locations[-1][locations[-1] == self.possible_locations.index('busy')] = \
                    self.possible_locations.index(person.office)

        location_matrix = np.vstack(locations)
        all_commands = list()

        for zone in valid_zones:
            i = self.possible_locations.index(zone)
            occupancy = np.sum(location_matrix == i, axis=0)

            result_command = {"Name": f"Generated_Schedule_Zone_{zone}",
                              "Schedule Type Limits Name": "Any Number",
                              "Field 1": "Through: 12/31",
                              "Field 2": "For: Weekdays"}

            counter = 3
            for t in range(1, 24 * 60 + 1):
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
        return all_commands, location_matrix, self.possible_locations

    # def generate_weekday_schedule(self, add_to_model=True):
    #     all_commands = list()
    #     for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
    #         one_day_commands = self.generate_daily_schedule(add_to_model=False)



class Person:
    def __init__(self, generator, office=None):
        self.office = office
        self.position = np.zeros(generator.day_cut_off)
        self.source = generator

    def customer_come(self, start_time, end_time, dest):
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
        they leave. Each person target to come at 8:30 am and leave at 5 pm, with a exponential distribution where
        mu = 30 minute. Use exponential distribution because people tend to come/leave on time with a very small
        chance of being late. In the meantime, assume that people directly goes into their own office right away.
        They require some time to walk to their office.
        :return: True if come to work, False otherwise
        """
        self.position = np.zeros(self.source.day_cut_off)
        # Decide absence
        if np.random.random() < self.source.call_for_absence:
            return False
        else:
            # Decide when come to office
            arrival_time = (self.source.start_work - self.source.come_leave_flex_coef) + \
                           int(np.random.exponential(self.source.come_leave_flex_coef))
            if arrival_time > self.source.cut_off_time:
                return False
            else:
                # Decide when go back home
                leave_time = self.source.end_work + int(np.random.exponential(self.source.come_leave_flex_coef))
                if leave_time >= self.source.day_cut_off:
                    leave_time = self.source.day_cut_off - 1

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
        # Usually go for lunch immediately, with average delay of 5 minute
        lunch_delay = int(np.random.exponential(5 * 60))
        lunch_delay = max(lunch_delay, 20 * 60)

        pass_zones = self.source.get_path(self.office, self.source.lunch_room)
        pass_zones.pop(0)
        zone_move_timer = [self.source.lunch_start_time]
        # TODO: Trespass time
        temp_timer = self.source.lunch_start_time + lunch_delay
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
        # Arrive maximum 3 min early, 2 min late
        meeting_attend = int(np.random.exponential(3 * 60))
        meeting_attend = self.source.daily_report - max(meeting_attend, 5 * 60)

        pass_zones = self.source.get_path(self.office, self.source.meeting_room)
        pass_zones.pop(0)
        zone_move_timer = [meeting_attend]
        # TODO: Trespass time
        temp_timer = meeting_attend
        for _ in pass_zones[:-1]:
            temp_timer = temp_timer - 3 + get_white_bias(1)
            zone_move_timer.insert(0, temp_timer)

        zone_move_timer.append(self.source.daily_report +
                               int(np.random.normal(self.source.daily_report_mean, self.source.daily_report_std)))

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
        return np.sum(self.position[start:end] == self.source.possible_locations.index(self.office)) == (end - start)

    def get_in_office_range(self):
        in_office = np.concatenate(([0],
                                    np.equal(self.position,
                                             self.source.possible_locations.index(self.office)).view(np.int8),
                                    [0]))
        absdiff = np.abs(np.diff(in_office))
        # Runs start and end where absdiff is 1.
        ranges = np.where(absdiff == 1)[0].reshape(-1, 2)
        return ranges

    def handle_customer(self, num_customer):
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
        for _ in range(np.random.poisson(self.source.visit_colleague)):
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

    def generate_daily_route(self, customer_list):
        time_list = list()
        self.generate_lunch()
        self.generate_daily_meeting()
        for num_customer in customer_list:
            time_list.append(self.handle_customer(num_customer))
        self.generate_go_other_office()
        return time_list

    def get_position(self, sec):
        if self.position[sec] == self.source.possible_locations.index("busy"):
            return self.office
        return self.source.possible_locations[int(self.position[sec])]

    def get_trigger(self):
        pass


def get_white_bias(second):
    return np.random.randint(second * 2 + 1) - second


def main():
    all_people = generate_daily_data()
    for person in all_people:
        print(person.position.size)
        # print(list(person.position))

    # current = start_synthetic_data
    # all_people = list()
    # results = dict()
    # for _ in range(int((end_synthetic_data - start_synthetic_data) / report_interval)):
    #     # print(current)
    #     results[str(current)[-8:].replace(':', '_')] = dict()
    #     if current.hour + current.minute + current.second == 0:
    #         # Generate a whole day data
    #         all_people = generate_daily_data()
    #     # for person in all_people:
    #     #     print(person.get_position(current.second + 60 * current.minute + 60 * 60 * current.hour))
    #
    #     current += report_interval
    #
    #     if current.hour + current.minute + current.second == 0:
    #         time_str = str(current)[:10].replace(' ', '_').replace('-', '_')
    #         with open(f"output/{time_str}", 'w') as json_out:
    #             json.dump(results, json_out)
    #         results = dict()


if __name__ == '__main__':
    main()
