import mpu
import folium
import requests
import simplejson
import urllib
import pandas as pd
import numpy as np
from pprint import pprint
from google.transit import gtfs_realtime_pb2


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
    
    def add_bus_location(self, loc: tuple[float, float]):
        self.loc = loc


def get_current_feed() -> gtfs_realtime_pb2.FeedMessage:
    feed = gtfs_realtime_pb2.FeedMessage()
    # requests will fetch the results from a url
    response = requests.get('http://track.ua-gis.com/gtfs/lviv/vehicle_position')
    feed.ParseFromString(response.content)
    
    return feed

def get_route_id(bus_num: str) -> int:
    
    # gets the info about routes
    df = pd.read_csv('data/routes.txt')
    df = df[df['route_short_name'] == f'А{bus_num}']
    return int(df.iloc[0][0])


def get_nearest_stop(request_loc: tuple[float, float]):
    '''
    Returns the nearest spot
    '''

    df = pd.read_csv('data/stops.txt')
    df['coords'] = list(zip(df['stop_lat'], df['stop_lon']))
    df['distances'] = [mpu.haversine_distance(request_loc, coords) for coords in df['coords']]
    df = df.sort_values(by='distances')
 
    nearest_stop = df.iloc[0].tolist()
    return nearest_stop[2:]

def get_time_to_arival(req: UserRequest) -> tuple[float, str]:
    
    feed = get_current_feed()

    bus_id = get_route_id(req.bus_num)
    nearest_stop = get_nearest_stop(req.loc)

    buses = [bus for bus in feed.entity if bus.vehicle.trip.route_id == str(bus_id)]

    distances = {}
    for bus in buses:
        coords = [bus.vehicle.position.latitude, bus.vehicle.position.longitude]
        distances[bus.id] = mpu.haversine_distance(nearest_stop[-2], coords)


    distances = sorted(distances.items(), key=lambda x: x[1])

    nearest_bus_id = distances[0][0]


    nearest_bus = [bus for bus in buses if bus.id == nearest_bus_id][0]


    orig_coord = nearest_stop[-2]
    dest_coord = nearest_bus.vehicle.position.latitude, nearest_bus.vehicle.position.longitude
    url = "https://maps.googleapis.com/maps/api/distancematrix/json?origins={0}&destinations={1}&mode=transit&language=en-EN&sensor=false&key=AIzaSyC3L0S5P8PDzHEcFqlHAryjcB-419zIaqk".format(f'{orig_coord[0]},{orig_coord[1]}',f'{dest_coord[0]},{dest_coord[1]}')
    result= simplejson.load(urllib.request.urlopen(url))

    return (result['rows'][0]['elements'][0]['duration']['text'], nearest_stop)
