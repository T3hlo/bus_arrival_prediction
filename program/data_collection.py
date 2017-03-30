"""
Data collection process file. Try to improve the efficiency.
Exported files: `weather.csv`, `segment.csv`, `api_data.csv` and `route_stop_dist.csv`
Input files: gtfs file, historical data
"""

# import modules
import pandas as pd
import numpy as np
import os
import requests
import csv
import random
from datetime import datetime, timedelta, date
from dateutil.rrule import rrule, DAILY

# set the path
path = '../'

print "working path"
print os.getcwd()
print os.listdir(path)


#################################################################################################################
#                                weather.csv                                                                    #
#################################################################################################################
def get_precip(gooddate):
    """
    Download the weather information for a specific date
    :param gooddate: date for downloading
    :return: list of the data
    """
    urlstart = 'http://api.wunderground.com/api/d083880ff5428216/history_'
    urlend = '/q/NY/New_York.json'

    url = urlstart + str(gooddate) + urlend
    data = requests.get(url).json()
    result = None
    for summary in data['history']['dailysummary']:
        result = [gooddate, summary['date']['year'], summary['date']['mon'], summary['date']['mday'], summary['fog'],
                  summary['rain'], summary['snow']]
    return result


def download_weather(date_start, date_end):
    """
    download the weather information for a date range
    :param date_start: start date, string, ex: '20160101'
    :param date_end: similar to date_start
    :return: list of the table record
    """

    a = datetime.strptime(date_start, '%Y%m%d')
    b = datetime.strptime(date_end, '%Y%m%d')

    result = [['date', 'year', 'month', 'day', 'fog', 'rain', 'snow']]
    for dt in rrule(DAILY, dtstart=a, until=b):
        current_data = get_precip(dt.strftime("%Y%m%d"))
        if current_data is None:
            continue
        else:
            result.append(current_data)

    # export to the csv file
    with open('weather.csv', 'wb') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=',')
        for item in result:
            spamwriter.writerow(item)

    return result


#################################################################################################################
#                                route_stop_dist.csv                                                            #
#################################################################################################################
"""
Calcualte the distance of each stops for a specific route from the initial stop.

It will read three different files: trips.txt, stop_times.txt and history file.
Use the stop_times.txt and trips.txt file to obtain the stop sequence for each route and use the historical data to calculate the actual distance for each stop.
If the specific stop has no records for the distance, we will use the average value as the result like calculating the travel duration.

Since the dist_along_route in the history data is actually the distance between the next_stop and the intial stop, which decrease the difficulty a lot.
"""


def read_data(route_num=None, direction_id=0):
    # type: (object, object) -> object
    """
    Read all the corresponding data according to the requirements: number of the routes we need to calcualte.
    Input: route_num
    Output: Three different dataframe:
    trips, stop_times, history. All of these three data should have been filtered according to the trip_id and route_id
    """
    trips = pd.read_csv(path + 'data/GTFS/gtfs/trips.txt')
    stop_times = pd.read_csv(path + 'data/GTFS/gtfs/stop_times.txt')
    # Obtain the filterd trips dataframe
    route_list = list(trips.route_id)
    non_dup_route_list = sorted(list(set(route_list)))
    if route_num is None:
        selected_routes = non_dup_route_list
    else:
        selected_routes = non_dup_route_list[:route_num]
    result_trips = trips[(trips.route_id.isin(selected_routes)) & (trips.direction_id == direction_id)]
    # Obtain the filtered stop_times dataframe
    selected_trips_var = set(list(result_trips.trip_id))
    result_stop_times = stop_times[stop_times.trip_id.isin(selected_trips_var)]
    # Obtain the filtered history dataframe
    file_list = os.listdir(path + 'data/history/')
    file_list.sort()
    history_list = []
    for single_file in file_list:
        if not single_file.endswith('.csv'):
            continue
        else:
            current_history = pd.read_csv(path + 'data/history/' + single_file)
            tmp_history = current_history[current_history.trip_id.isin(selected_trips_var)]
            if len(tmp_history) == 0:
                continue
            else:
                print "historical file name: ", single_file
                history_list.append(tmp_history)
    result_history = pd.concat(history_list)
    print "complete reading data"
    return result_trips, result_stop_times, result_history


def calculate_stop_distance(trips, stop_times, history, direction_id=0):
    """
    Calculate the distance of each stop with its initial stop. Notice that the dist_along_route is the distance between the next_stop and the initial stop
    Input: three filtered dataframe, trips, stop_times, history
    Output: One dataframe, route_stop_dist
    The format of the route_stop_dist:
    route_id    direction_id    stop_id    dist_along_route
    str         int             int        float
    """
    result = pd.DataFrame(columns=['route_id', 'direction_id', 'stop_id', 'dist_along_route'])
    selected_routes = set(trips.route_id)
    # Looping from each route to obtain the distance of each stops
    for single_route in selected_routes:
        print "route name: ", single_route
        selected_trips_var = set(trips[trips.route_id == single_route].trip_id)
        stop_sequence = list(stop_times[stop_times.trip_id == list(selected_trips_var)[0]].stop_id)
        result.loc[len(result)] = [single_route, int(direction_id), int(stop_sequence[0]), 0.0]
        selected_history = history[history.trip_id.isin(selected_trips_var)]
        for i in range(1, len(stop_sequence)):
            stop_id = stop_sequence[i]
            current_history = selected_history[selected_history.next_stop_id == stop_id]
            if float(stop_id) == float(result.iloc[-1].stop_id):
                continue
            elif len(current_history) == 0:
                dist_along_route = -1.0
            else:
                current_dist = []
                for j in range(len(current_history)):
                    current_dist.append(current_history.iloc[j].dist_along_route)
                dist_along_route = sum(current_dist) / float(len(current_dist))
            result.loc[len(result)] = [single_route, int(direction_id), int(stop_id), dist_along_route]
    result.to_csv('original_route_stop_dist.csv')
    # Since some of the stops might not record, it is necessary to check the dataframe again.
    # Because of the bug or other reasons, some of the routes have a long jump in the stop list, we should remove the corresponding stop list
    count = 1
    prev = 0
    remove_route_list = set()
    for i in range(1, len(result) - 1):
        if result.iloc[i].dist_along_route == -1:
            if result.iloc[i - 1].dist_along_route != -1:
                prev = result.iloc[i - 1].dist_along_route
            count += 1
        else:
            if count != 1:
                if count >= 4:
                    remove_route_list.add(result.iloc[i - 1].route_id)
                distance = (float(result.iloc[i].dist_along_route) - float(prev)) / float(count)
                while count > 1:
                    result.iloc[i - count + 1, result.columns.get_loc('dist_along_route')] = result.iloc[
                                                                                                 i - count].dist_along_route + float(
                        distance)
                    count -= 1
            else:
                continue
    result.to_csv('original_improve_route_stop_dist.csv')
    result = result[~result.route_id.isin(remove_route_list)]
    return result


#################################################################################################################
#                                        segment.csv                                                            #
#################################################################################################################
"""
Generate the orgininal segment data including the travel duration. Improve the segment data by adding back the skipped
"""


def extract_time(time):
    """
    example of time(str): '2017-01-16T15:09:28Z'
    """
    result = datetime.strptime(time[11: 19], '%H:%M:%S')
    return result


def calculate_time_span(time1, time2):
    """
    Calculate the duration of two timepoints
    :param time1: previous time point, ex: '2017-01-16T15:09:28Z'
    :param time2: next time point, ex: '2017-01-16T15:09:28Z'
    :return: float number of seconds
    """
    timespan = extract_time(time2) - extract_time(time1)
    return timespan.total_seconds()


def select_trip_list(num_route=None, direction_id=0):
    """
    Generate the list of the trip id for the selected routes
    :param num_route: the number of the selected routes. If the num_route is None, then all the route id will be selected
    :param direction_id: the direction id can be 0 or 1
    :return: the list of the trip_id
    """
    # Read the GTFS data
    # data source: MTA, state island, Jan, 4, 2016
    trips = pd.read_csv(path + 'data/GTFS/gtfs/trips.txt')
    route_stop_dist = pd.read_csv('route_stop_dist.csv')

    # select a specific route and the corresponding trips
    route_list = list(route_stop_dist.route_id)
    non_dup_route_list = sorted(list(set(route_list)))
    if num_route is None:
        select_routes = non_dup_route_list
    else:
        select_routes = non_dup_route_list[:num_route]
    selected_trips_var = []
    for route in select_routes:
        selected_trips_var += list(trips[(trips.route_id == route) & (trips.direction_id == direction_id)].trip_id)
    return selected_trips_var


def filter_history_data(date_start, date_end, selected_trips_var):
    # type: (object, object, object) -> object
    """
    Filtering the historical data to remove the unselected trips
    :rtype: object
    :param date_start: start date for historical date, int, yyyymmdd, ex: 20160109
    :param date_end: end date for historical date. Similar to date_start. The date_start and the date_end are included.
    :param selected_trips_var: the list of the trip_id for the selected routes
    :return: dataframe for the filtered historical data
    """
    # List the historical file
    file_list_var = os.listdir(path + 'data/history/')
    file_list_var.sort()
    history_list = []
    print "filtering historical data"
    for filename in file_list_var:
        if not filename.endswith('.csv'):
            continue
        if filename[9:17] < str(date_start) or filename[9:17] > str(date_end):
            continue
        print filename
        ptr_history = pd.read_csv(path + 'data/history/' + filename)
        tmp_history = ptr_history[
            (ptr_history.trip_id.isin(selected_trips_var)) & (ptr_history.dist_along_route != '\N') & (
                ptr_history.dist_along_route != 0) & (ptr_history.progress == 0)]
        history_list.append(tmp_history)
    result = pd.concat(history_list)
    return result


def add_weather_info(weather, date_var):
    """
    add the weather information from the file: weather.csv
    The weather are expressed as below:
    0: sunny
    1: rainy
    2: snowy
    :param weather: the dataframe for weather.csv file
    :param date_var: the date for querying the weather
    :return: return the weather value today.
    """
    ptr_weather = weather[weather.date == date_var]
    if ptr_weather.iloc[0].snow == 1:
        weather_today = 2
    elif ptr_weather.iloc[0].rain == 1:
        weather_today = 1
    else:
        weather_today = 0
    return weather_today


def generate_original_segment(full_history_var, weather, stop_times_var):
    """
    Generate the original segment data
    Algorithm:
    Split the full historical data according to the service date, trip_id with groupby function
    For name, item in splitted historical dataset:
        service date, trip_id = name
        Split the item according to the vehicle_id, keep the data with the larget length of list for the vehicle_id
        calcualte the travel duration within the segement of this segment df and save the result into list
    concatenate the list
    :param full_history_var: the historical data after filtering
    :param weather: the dataframe for the weather information
    :param stop_times_var: the dataframe from stop_times.txt
    :return: dataframe for the original segment
    """
    grouped = list(full_history_var.groupby(['service_date', 'trip_id']))
    print len(grouped)
    result_list = []
    for index in range(len(grouped)):
        name, single_history = grouped[index]
        if index % 150 == 0:
            print index
        service_date, trip_id = name
        if service_date <= 20160103:
            continue
        grouped_vehicle_id = list(single_history.groupby(['vehicle_id']))
        majority_length = -1
        majority_vehicle = -1
        majority_history = single_history
        for vehicle_id, item in grouped_vehicle_id:
            if len(item) > majority_length:
                majority_length = len(item)
                majority_history = item
                majority_vehicle = vehicle_id
        stop_sequence = [item for item in list(stop_times_var[stop_times_var.trip_id == trip_id].stop_id)]
        current_segment_df = generate_original_segment_single_history(majority_history, stop_sequence)
        if current_segment_df is None:
            continue
        current_weather = add_weather_info(weather, service_date)
        current_segment_df['weather'] = current_weather
        day_of_week = datetime.strptime(str(service_date), '%Y%m%d').weekday()
        current_segment_df['service_date'] = service_date
        current_segment_df['day_of_week'] = day_of_week
        current_segment_df['trip_id'] = trip_id
        current_segment_df['vehicle_id'] = majority_vehicle
        result_list.append(current_segment_df)
    if result_list != []:
        result = pd.concat(result_list)
    else:
        return None
    return result


def generate_original_segment_single_history(history, stop_sequence):
    """
    Calculate the travel duration for a single historical data
    Algorithm:
    Filter the historical data with the stop sequence here
    arrival_time_list = []
    for i = 1, len(history) - 1:
        use prev and the next to mark the record:
            prev = history[i - 1]
            next = history[i]
        calculate the distance for prev and next respectively:
            prev_distance = prev.dist_along_route - prev.dist_from_stop
            next_distance = next.dist_along_route - next.dist_from_stop
        if prev_distance == next_distance or prev_distance = 0, continue to next row
        distance_ratio = prev.dist_from_stop / (next_distance - prev_distance)
        calcualte the time duration between the two spot:
            prev_time = datetime.strptime(prev.timestamp, '%Y-%m-%dT%H:%M:%SZ')
            next_time = ...
            travel_duration = next_time - prev_time
        current_arrival_duration = travel_duration * distance_ratio
        current_arrival_time = current_arrival_duration + prev_time
        arrival_time_list.append((prev.next_stop_id, current_arrival_time))
    result = pd.Dataframe
    for i in range(1, len(arrival_time_list)):
        prev = arrival_time_list[i - 1]
        next = arrival_time_list[i]
        segment_start, segment_end obtained
        travel_duration = next[1] - prev[1]
        timestamp = prev[1]
        service_date = history[0].service_date
        ...
        save the record to result

    :param history: single historical data
    :param stop_sequence: stop sequence for the corresponding trip id
    :return: the dataframe of the origianl segment dataset
    """
    history = history[history.next_stop_id.isin(stop_sequence)]
    if len(history) < 3:
        return None
    arrival_time_list = []
    i = 1
    while i < len(history):
        prev_record = history.iloc[i - 1]
        next_record = history.iloc[i]
        while i < len(history) and stop_sequence.index(prev_record.next_stop_id) >= stop_sequence.index(next_record.next_stop_id):
            i += 1
            if i == len(history):
                break
            if stop_sequence.index(prev_record.next_stop_id) == stop_sequence.index(next_record.next_stop_id):
                prev_record = next_record
            next_record = history.iloc[i]
        if i == len(history):
            break
        # calculate the distance for prev and next respectively
        prev_distance = float(prev_record.dist_along_route) - float(prev_record.dist_from_stop)
        next_distance = float(next_record.dist_along_route) - float(next_record.dist_from_stop)
        if prev_distance == next_distance or prev_distance == 0:
            i += 1
            continue
        else:
            distance_ratio = float(prev_record.dist_from_stop) / (next_distance - prev_distance)
        # calcualte the time duration between the two spot
        prev_time = datetime.strptime(prev_record.timestamp, '%Y-%m-%dT%H:%M:%SZ')
        next_time = datetime.strptime(next_record.timestamp, '%Y-%m-%dT%H:%M:%SZ')
        travel_duration = next_time - prev_time
        travel_duration = travel_duration.total_seconds()
        # add it into the arrival time list
        current_arrival_duration = travel_duration * distance_ratio
        current_arrival_time = timedelta(0, current_arrival_duration) + prev_time
        arrival_time_list.append((prev_record.next_stop_id, current_arrival_time))
        i += 1
    result = pd.DataFrame(columns=['segment_start', 'segment_end', 'timestamp', 'travel_duration'])
    for i in range(1, len(arrival_time_list)):
        prev_record = arrival_time_list[i - 1]
        next_record = arrival_time_list[i]
        segment_start, segment_end = prev_record[0], next_record[0]
        timestamp = prev_record[1]
        travel_duration = next_record[1] - prev_record[1]
        travel_duration = travel_duration.total_seconds()
        result.loc[len(result)] = [segment_start, segment_end, timestamp, travel_duration]
    return result




def improve_dataset_unit(single_trip, date_var, stop_sequence, segment_df):
    """
    This funciton is used to improve the dataset for a specific trip_id at a spacific date.
    """
    df = pd.DataFrame(
        columns=['segment_start', 'segment_end', 'segment_pair', 'time_of_day', 'day_of_week', 'date', 'weather',
                 'trip_id', 'travel_duration'])
    current_segmen_pair = segment_df[(segment_df.trip_id == single_trip) & (segment_df.date == date_var)]
    for i in xrange(1, len(current_segmen_pair)):
        segment_start = int(current_segmen_pair.iloc[i - 1].segment_start)
        segment_end = int(current_segmen_pair.iloc[i].segment_start)
        start_idx = stop_sequence.index(segment_start)
        end_idx = stop_sequence.index(segment_end)
        if end_idx - start_idx == 1:
            df.loc[len(df)] = current_segmen_pair.iloc[i - 1]
        else:
            skipped_stops = stop_sequence[start_idx + 1:end_idx]
            number_travel_duration = len(skipped_stops) + 1
            arrival_time1 = datetime.strptime(current_segmen_pair.iloc[i - 1].time_of_day, '%H:%M:%S')
            arrival_time2 = datetime.strptime(current_segmen_pair.iloc[i].time_of_day, '%H:%M:%S')
            timespan = arrival_time2 - arrival_time1
            total_duration = timespan.total_seconds()
            average_duration = total_duration / float(number_travel_duration)
            estimated_travel_time = timedelta(0, average_duration)
            tmp_total_stops = [segment_start] + skipped_stops + [segment_end]
            for j in xrange(len(tmp_total_stops) - 1):
                segment_start = tmp_total_stops[j]
                segment_end = tmp_total_stops[j + 1]
                segment_pair = (segment_start, segment_end)
                previous_arrival_time = current_segmen_pair.iloc[i - 1].time_of_day
                estimated_arrival_time = datetime.strptime(previous_arrival_time, '%H:%M:%S')
                for count in range(j):
                    estimated_arrival_time += estimated_travel_time
                time_of_day = str(estimated_arrival_time)[11:19]
                day_of_week = current_segmen_pair.iloc[0].day_of_week
                weather = current_segmen_pair.iloc[0].weather
                trip_id = single_trip
                travel_duration = average_duration
                df.loc[len(df)] = [segment_start, segment_end, segment_pair, time_of_day, day_of_week, date_var,
                                   weather,
                                   trip_id, travel_duration]
    return df


def improve_dataset():
    """
    algorithm:
    for each specific trip_id:
        obtain the date_list
        obtain the stop_sequence
        for each date in date_list:
            build the dataframe
            obtain the current_segment_pair for the specific trip_id and date
            obtain the segment_start sequence
            for each segment_start in the segment_start sequence:
                find the corresponding index in the stop_sequence
                find the index of the segment_end in the corresponding segment_pair
                if the indices of these two are i and i + 1:
                    add the segment_pair into the new dataframe as the result
                else:
                    use the index to find all the skipped stops from the stop_sequence
                    calculate the number of skipped travel duration within this segment
                    use the average value as the travel duration and add the stop arrival time for each skipped stops
                    add the segment_pair into the new dataframe as the result

    """
    segment_df = pd.read_csv('original_segment.csv')
    stop_times = pd.read_csv(path + 'data/GTFS/gtfs/stop_times.txt')

    trips = set(segment_df.trip_id)
    print "length of the trips: ", len(trips)
    df_list = []
    for i, single_trip in enumerate(trips):
        if i % 50 == 0:
            print "index = ", i, single_trip
        date_list = list(set(segment_df[segment_df.trip_id == single_trip].date))
        stop_sequence = list(stop_times[stop_times.trip_id == single_trip].stop_id)
        for date_var in date_list:
            df = improve_dataset_unit(single_trip, date_var, stop_sequence, segment_df)
            df_list.append(df)
    result = pd.concat(df_list)
    return result


#################################################################################################################
#                                    API data                                                                   #
#################################################################################################################
"""
Generate the api data from the GTFS data and the historical data
"""
def generate_api_data(date_list, time_list, route_list, stop_num, route_stop_dist, full_history = None):
    """
    Generate the api data for the test_route_set and given time list
    :param time_list: the time list for testing, ['12:00:00', '12:05:00', ...]
    :param route_list: the list for the test route id
    :param stop_num: the number of the stop id for test
    :param route_stop_dist: the dataframe for the route_stop_dist.csv file
    :return: the dataframe for the api data
    trip_id    vehicle_id    route_id    stop_id    time_of_day    date    dist_along_route
    
    Algorithm:
    Read the full historical data for testing
    Determine the test routes (2 ~ 4), and the corresponding stop sequence
    
    Generate the set of trip id for test routes
    Generate the random test stop id for each test routes
    Filtering the historical data with trip id, NAN
    Generate the list of historical data Groupby(date, trip id)
    for each item in the list of the historical data:
        obtain the trip id and the date
        obtain the correspnding route
        obtain the corresponding stop set
        for stop in stop set:
            for each time point in the time list:
                check whether the bus has passed the stop at the time point
                if yes, continue to next stop
                otherwise, save the record into result
    """
    trips = pd.read_csv(path + 'data/GTFS/gtfs/trips.txt')
    trip_route_dict = {}
    route_stop_dict = {}
    for route in route_list:
        print route
        stop_sequence = list(route_stop_dist[route_stop_dist.route_id == route].stop_id)
        if len(stop_sequence) < 5:
            continue
        trip_set = set(trips[trips.route_id == route].trip_id)
        current_dict = dict.fromkeys(trip_set, route)
        trip_route_dict.update(current_dict)
        stop_set = set()
        for i in range(stop_num):
            stop_set.add(stop_sequence[random.randint(2, len(stop_sequence) - 2)])
        route_stop_dict[route] = stop_set
    if full_history is None:
        full_history = pd.read_csv('full_history.csv')
    history = full_history[full_history.trip_id.isin(trip_route_dict.keys())]
    history_grouped = history.groupby(['service_date', 'trip_id'])
    result = pd.DataFrame(columns=['trip_id', 'vehicle_id', 'route_id', 'stop_id', 'time_of_day', 'date', 'dist_along_route'])
    print_dict = dict.fromkeys(date_list, True)
    for name, single_history in list(history_grouped):
        date, single_trip = name
        if date not in date_list:
            continue
        if print_dict[date]:
            print date
            print_dict[date] = False
        route_id = trip_route_dict[single_trip]
        stop_set = [str(int(item)) for item in route_stop_dict[route_id]]
        stop_sequence = [str(int(item)) for item in list(route_stop_dist[route_stop_dist.route_id == route_id].stop_id)]
        tmp_history = single_history[(single_history.next_stop_id.isin(stop_sequence)) & (single_history.dist_along_route > '0')]
        if len(tmp_history) < 3:
            continue
        else:
            single_history = pd.DataFrame(columns=tmp_history.columns)
            for i in range(1, len(tmp_history)):
                if float(tmp_history.iloc[i - 1].dist_along_route) < float(tmp_history.iloc[i].dist_along_route):
                    single_history.loc[len(single_history)] = tmp_history.iloc[i - 1]
            if len(single_history) < 3:
                continue
            if tmp_history.iloc[-1].dist_along_route >= single_history.iloc[-1].dist_along_route:
                single_history.loc[len(single_history)] = tmp_history.iloc[-1]
        for target_stop in stop_set:
            target_index = stop_sequence.index(target_stop)
            for current_time in time_list:
                #  check whether the bus has passed the target stop, if yes, break and continue to the next target_stop
                index = 1
                while index < len(single_history) and single_history.iloc[index].timestamp[11:19] <= current_time:
                    index += 1
                if index == len(single_history):
                    break
                index -= 1
                tmp_stop = str(single_history.iloc[index].next_stop_id)
                tmp_index = stop_sequence.index(tmp_stop)
                if tmp_index > target_index:
                    break
                # If the bus has not started from the initial stop yet, continue to next time point in the time list
                if single_history.iloc[0].timestamp[11:19] > current_time:
                    continue
                # If the bus does not pass the target stop, save the remained stops into the stop sequence and calculate the result
                current_list = generate_single_api(current_time, route_stop_dist, route_id, single_history[index:], target_stop, target_index)
                if current_list is not None:
                    result.loc[len(result)] = current_list
    return result





"""
algorithm for calculate the single record:
According to the time point, find the closest time duration (prev, next)
Calculate the dist_along_route for the bus at the time point:
    calculate the space distance between the time duration (prev, next)
    calculate the time distance of two parts: (prev, current), (prev, next)
    use the ratio of the time distance to multiply with the space distance to obtain the dist_along_route for current
According to the dista_along_route and the stop sequence confirm the remained stops including the target stop
Count the number of the remained stops
"""
def generate_single_api(current_time, route_stop_dist, route_id, single_history, stop_id, end_index):
    """
    Calculate the single record for the api data
    :param current_time: The current time for generating the api data
    :param single_history: The historical data for the specific date and the trip id
    :param stop_id: The target stop id
    :return: the list for the result
    [trip_id    vehicle_id    route_id    time_of_day    date    dist_along_route]
    
    Algorithm for calculate the single record:
    According to the time point, find the closest time duration (prev, next)
    Calculate the dist_along_route for the bus at current timepoint:
        calculate the space distance between the time duration (prev, next)
        calculate the time distance of two parts: (prev, current), (prev, next)
        use the ratio of the time distance to multiply with the space distance to obtain the dist_along_route for current
    According to the dista_along_route and the stop sequence confirm the remained stops including the target stop
    Count the number of the remained stops
    """
    single_trip = single_history.iloc[0].trip_id
    prev = single_history.iloc[0]
    next = single_history.iloc[1]
    # If the time duration between the prev and the next time point is larger than 5 minutes, ignore it for precision
    if calculate_time_span(prev['timestamp'], next['timestamp']) > 300:
        return None
    # calculate the dist_along_route for current
    distance_prev_next = (float(next['dist_along_route']) - float(next['dist_from_stop'])) - (float(prev['dist_along_route']) - float(prev['dist_from_stop']))
    time_duration_prev_next = calculate_time_span(prev['timestamp'], next['timestamp'])
    time_duration_prev_current = datetime.strptime(current_time, '%H:%M:%S') - extract_time(prev['timestamp'])
    time_duration_prev_current = time_duration_prev_current.total_seconds()
    ratio = float(time_duration_prev_current) / float(time_duration_prev_next)
    distance_prev_current = float(distance_prev_next) * ratio
    dist_along_route = (float(prev['dist_along_route']) - float(prev['dist_from_stop'])) + distance_prev_current
    # Generate the return list
    # trip_id    vehicle_id    route_id    stop_id    time_of_day    date    dist_along_route
    result = [single_trip, prev['vehicle_id'], route_id, stop_id, current_time, prev['service_date'], dist_along_route]
    return result


#################################################################################################################
#                                    debug section                                                              #
#################################################################################################################
# date_list = range(20160125, 20160130)
# route_stop_dist = pd.read_csv('route_stop_dist.csv')
# stop_num = 2
# route_list = ['X14', 'X11', 'X42', 'S66']
# history_list = []
# for current_date in date_list:
#     filename = 'bus_time_' + str(current_date) + '.csv'
#     history_list.append(pd.read_csv(path + 'data/history/' + filename))
# full_history = pd.concat(history_list)
# time_list = ['12:00:00', '12:05:00', '12:10:00', '12:15:00', '12:20:00', '12:25:00', '12:30:00']
# api_data = generate_api_data(date_list, time_list, route_list, stop_num, route_stop_dist, full_history)


#################################################################################################################
#                                    main function                                                              #
#################################################################################################################


if __name__ == '__main__':
    file_list = os.listdir('./')
    # download weather information
    if 'weather.csv' not in file_list:
        print "download weather.csv file"
        download_weather('20160101', '20160131')
        print "complete downloading weather information"
    # export the route dist data
    if 'route_stop_dist.csv' not in file_list:
        print "export route_stop_dist.csv file"
        trips, stop_times, history = read_data()
        route_stop_dist = calculate_stop_distance(trips, stop_times, history)
        route_stop_dist.to_csv('route_stop_dist.csv')
        print "complete exporting the route_stop_dist.csv file"
    # export the segment data
    if 'original_segment.csv' not in file_list:
        print "export original_segment.csv file"
        selected_trips = select_trip_list()
        weather_df = pd.read_csv('weather.csv')
        full_history = filter_history_data(20160104, 20160123, selected_trips)
        stop_times = pd.read_csv(path + 'data/GTFS/gtfs/stop_times.txt')
        segment_df = generate_original_segment(full_history, weather_df, stop_times)
        segment_df.to_csv('original_segment.csv')
        print "complete exporting the original_segement.csv file"
    if 'segment.csv' not in file_list:
        print "export segment.csv file"
        segment_df = improve_dataset()
        segment_df.to_csv('segment.csv')
        print "complete exporting the segment.csv file"
    # export the api data
    if 'api_data.csv' not in file_list:
        print "export api_data.csv file"
        date_list = range(20160125, 20160130)
        route_stop_dist = pd.read_csv('route_stop_dist.csv')
        stop_num = 4
        route_list = list(set(route_stop_dist.route_id))
        history_list = []
        for current_date in date_list:
            filename = 'bus_time_' + str(current_date) + '.csv'
            history_list.append(pd.read_csv(path + 'data/history/' + filename))
        full_history = pd.concat(history_list)
        api_data_list = []
        time_list = ['12:00:00', '12:05:00', '12:10:00', '12:15:00', '12:20:00', '12:25:00', '12:30:00']
        current_api_data = generate_api_data(date_list, time_list, route_list, stop_num, route_stop_dist, full_history)
        api_data_list.append(current_api_data)
        time_list = ['18:00:00', '18:05:00', '18:10:00', '18:15:00', '18:20:00', '18:25:00', '18:30:00']
        current_api_data = generate_api_data(date_list, time_list, route_list, stop_num, route_stop_dist, full_history)
        api_data_list.append(current_api_data)
        api_data = pd.concat(api_data_list)
        api_data.to_csv('api_data.csv')
        print "complete exporting the api_data.csv file"
    print "complete data collection"
