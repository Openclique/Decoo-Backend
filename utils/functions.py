import numpy
import math
import livepopulartimes
import requests
from geolib import geohash

import dynamodb
from env.google_api import API_KEY

BASE_URL = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
TYPE = "bar"

def destinationPoint(lat, lng, brng, dist, index):
    '''
    This function returns the coordinates of a points of a direction
    on a radius around specific coordinates
    Returns:
    :direction: enum('n', 'ne', etc)
    :latitude: latitude coordinates
    :longitude: longitude coordinates
    :geohash: 10 digits geohash of the point
    '''

    rad = 6371                  # earths mean radius
    dist2 = dist/rad             # convert dist to angular distance in radians
    brng = numpy.deg2rad(brng)  # convert to radians
    lat1 = numpy.deg2rad(lat) 
    lon1 = numpy.deg2rad(lng)

    lat2 = math.asin(math.sin(lat1)*math.cos(dist2) + math.cos(lat1)*math.sin(dist2)*math.cos(brng) )
    lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(dist2)*math.cos(lat1),math.cos(dist2)-math.sin(lat1)*math.sin(lat2))
    lon2 = math.fmod(lon2 + 3*math.pi, 2*math.pi) - math.pi  # normalise to -180..+180º
    lat2 = numpy.rad2deg(lat2)
    lon2 = numpy.rad2deg(lon2)

    return lat2, lon2, geohash.encode(lat2, lon2, 10), dist

def getGeohashesInRadius(latitude, longitude, radius):
    '''
    This function takes in a latitude, a longitude, and a radius, and returns
    a list of geohashes at different precisions (5, 6, 7 digits)
    '''
    n = 16
    bearings = range(0, int(360-(360/n)), int(360/n)) # create array of all bearings needed from lat/lng

    points = [(latitude, longitude, geohash.encode(latitude, longitude, 10), 0)]

    # We get all the geohashes on the 8 cardinal points of a radius around us
    # We expand the radius to get as many different geohashes zones as possible
    for step in range(1, radius + 1):
        for index, brng in enumerate(bearings):
            points.append(destinationPoint(latitude, longitude, brng, step, index))
    
    track = {
        "five_digits": [],
        "six_digits": [],
        "seven_digits": []
    }

    # Then we keep track of how many different geohashes we have at different precision levels
    for _, _, h, _ in points:
        if h[:5] not in track["five_digits"]:
            track["five_digits"].append(h[:5])
        if h[:6] not in track["six_digits"]:
            track["six_digits"].append(h[:6])
        if h[:7] not in track["seven_digits"]:
            track["seven_digits"].append(h[:7])

    return track

def get_info_from_google_api(latitude, longitude):
    """This function takes in a latitude and a longitude, queris
    the google places API, then returns a list of places around current location.

    Args:
        latitude (string): Current user's latitude
        longitude (string): Currrent user's longitude

    Returns:
        [{obj}]: Returns a list of places around current user's location
    """

    # Building the base url
    url = f"{BASE_URL}location={latitude},{longitude}&radius={2400}&type={TYPE}&key={API_KEY}"

    # Making a request to google places api
    res = requests.get(url).json()

    return res["results"]

def get_places_around_location(latitude, longitude):
    """This function queries a list of locations around the user's position using its
    latitude and longitude. It then uses the livepopulartimes python framework to extract
    the popular hours and current popularity for the place.

    Args:
        latitude (string): Current user's latitude
        longitude (string): Current user's longitude

    Returns:
        [{obj}]: Returns a list of places around current user's location, with their live traffic
    """

    places = []

    # First we make an API call to google to get a list of places around current location
    google_search = get_info_from_google_api(latitude, longitude)

    # Then we make queries to livepopulartimes to get popular times + current popularity for each point
    for place in google_search:
        address = f"({place['name']}) {place['vicinity']}"
        to_add = livepopulartimes.get_populartimes_by_address(address)
        places.append(to_add)

    # And we return these informations
    return places

def fetchPlacesFromApis(geohashes):
    '''
    This function takes in a list of geohashes and queries informations from external APIs
    to put in our database
    :geohashes: ([str]) A list of 5 digits geohashes that we need to update
    Returns:
    :places: ([str]) A list of places informations
    '''

    places = []

    # We loop through all geohashes
    for geo in geohashes:

        # First we convert the geohash to lat lon
        coords = geohash.decode(geo)

        # Then we fetch the APIs to get places around this location
        new_places = get_places_around_location(coords.lat,coords.lon)

        # And we add them to the current list of places
        places.extend(new_places)

    # After that we loop through all the places we queried, and remove all duplicates
    final_places = []
    for place in places:
        if place not in final_places:
            final_places.append(place)

    # We save these informations in our database
    dynamodb.batchUpdatePlaces(final_places)

    # And we return all places

    return final_places