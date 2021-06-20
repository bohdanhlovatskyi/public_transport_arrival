import mpu
import folium
import requests
import simplejson
import urllib
import pandas as pd
import numpy as np
from pprint import pprint
from google.transit import gtfs_realtime_pb2
from telebot.types import User
from config import GoogleAPI
from typing import Tuple, List


class UserRequest:
    '''
    Class to manage requests.

    TODO: should be replaced with mongo
    '''

    def __init__(self) -> None:
        self.bus_num = None
        self.loc = None

    def add_bus_num(self, bus_num: str):
        self.bus_num = bus_num
    
    def add_user_location(self, loc: tuple[float, float]):
        self.loc = loc

    def __str__(self) -> str:
        return f'Bus {self.bus_num} is at {self.loc}'


def get_current_feed() -> gtfs_realtime_pb2.FeedMessage:
    '''
    Gets a file with info from the government site. Parses it according
    to the standart for such files developed by Google
    '''

    feed = gtfs_realtime_pb2.FeedMessage()
    # requests will fetch the results from a url
    response = requests.get('http://track.ua-gis.com/gtfs/lviv/vehicle_position')
    feed.ParseFromString(response.content)
    
    return feed

def get_route_id(request: UserRequest) -> int:
    
    # gets the info about routes
    df = pd.read_csv('data/routes.txt')
    df = df[df['route_short_name'] == f'А{request.bus_num}']
    return int(df.iloc[0][0])


def get_spots(request: UserRequest) -> pd.DataFrame:
    '''
    Returns the spots, sorted by their distance to the given coordinates by the user
    '''

    df = pd.read_csv('data/stops.txt')
    bus_stops_names, bus_stops_ids = get_all_the_stops(request.bus_num)
    df = df.loc[df['stop_id'].isin(bus_stops_ids)]

    df['coords'] = list(zip(df['stop_lat'], df['stop_lon']))
    df['distances'] = [mpu.haversine_distance(request.loc, coords) for coords in df['coords']]
    df = df.sort_values(by='distances')

    return df

def get_list_of_stops(request: UserRequest) -> List[str]:
    pass

def get_nearest_spot(request: UserRequest) -> Tuple[str, str, float, float, Tuple[float, float], float]:
    '''
    returns : (stop_name, stop_adress, lat, lon, (lat, lon), distance)
    '''

    spots = get_spots(request)

    nearest_stop = spots.iloc[0].tolist()
    print(nearest_stop[2:])
    return nearest_stop[2:]

def get_all_the_stops(bus_number: int) -> Tuple[list[str], list[int]]:
    '''
    Parses several files to get list of spots for certain bus
    '''

    routes = pd.read_csv('data/routes.txt')

    route_id = routes[routes['route_short_name'] == f'А{bus_number}'].iloc[0][0]
    
    trips = pd.read_csv('data/trips.txt')
    
    specific_route_trips = trips[trips['route_id'] == route_id]
    some_trip_id = specific_route_trips.iloc[0][2]

    stops = pd.read_csv('data/stop_times.txt')
    
    some_trip = stops[stops['trip_id'] == some_trip_id]
    
    # from some_trip_stops we can also receive arrival_time of each trip
    some_trip_stops = some_trip['stop_id'].tolist()

    stops_df = pd.read_csv('data/stops.txt')

    stop_names = []
    for idx, elm in enumerate(some_trip_stops):
        stop_names.append(stops_df[stops_df['stop_id'] == some_trip_stops[idx]]['stop_desc'].tolist()[0])
        
    return stop_names, some_trip_stops

def get_time_to_arival(req: UserRequest, direction: int = 0) -> tuple[float, str]:

    feed = get_current_feed()

    bus_id = get_route_id(req)
    nearest_stop = get_nearest_spot(req)

    buses = [bus for bus in feed.entity if bus.vehicle.trip.route_id == str(bus_id)]
    
    trips_description = pd.read_csv('data/trips.txt')

    distances = {}
    for bus in buses:
        coords = [bus.vehicle.position.latitude, bus.vehicle.position.longitude]
        trip = trips_description[trips_description['trip_id'] == bus.vehicle.trip.trip_id].iloc[0]
        trip_direction = int(trip['direction_id'])
        if direction != trip_direction:
            continue
        headsign = trip['trip_headsign']
        distances[bus.id] = (mpu.haversine_distance(nearest_stop[-2], coords), headsign)

    nearest_bus_info = sorted(distances.items(), key=lambda x: x[1][0])[0]

    nearest_bus_id, direction = nearest_bus_info[0], nearest_bus_info[1][1]

    nearest_bus = [bus for bus in buses if bus.id == nearest_bus_id][0]
    orig_coord = nearest_stop[-2]
    dest_coord = nearest_bus.vehicle.position.latitude, nearest_bus.vehicle.position.longitude
    url = "https://maps.googleapis.com/maps/api/distancematrix/json?origins={0}&destinations={1}&mode=transit&language=en-EN&sensor=false&key={2}".format(f'{orig_coord[0]},{orig_coord[1]}',f'{dest_coord[0]},{dest_coord[1]}', GoogleAPI)
    result= simplejson.load(urllib.request.urlopen(url))

    return result['rows'][0]['elements'][0]['duration']['text'], dest_coord, nearest_stop, direction

if __name__ == '__main__':
    req = UserRequest()
    req.add_bus_num(18)
    req.add_user_location((49.809545, 23.988369))

    res = get_time_to_arival(req)

    print(res)