import numpy
import math
import livepopulartimes
import requests
import os
from geolib import geohash
from decimal import Decimal

from utils import dynamodb

NEARBY_URL = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
DETAIL_URL = f"https://maps.googleapis.com/maps/api/place/details/json?"
TYPE = "bar"
# API_KEY=os.getenv("API_KEY")
API_KEY="AIzaSyAzdc-cory5ZG-Ds4lW3Y8a7D-UgKFlbC0" # Google Cloud Platform arnauze@gmail.com Openclique project

class number_str(float):
    def __init__(self, o):
        self.o = o
    def __repr__(self):
        return str(self.o)

def decimal_serializer(o):
    if isinstance(o, Decimal):
        return number_str(o)
    raise TypeError(repr(o) + " is not JSON serializable")

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

def get_place_info_from_google(place_id):
    """This function calls the place detail endpoint from
    google places API.

    Args:
        place_id (string): Id of the place to query
    """

    url = f"{DETAIL_URL}place_id={place_id}&key={API_KEY}"
    print(url)

    # Making a request to google places api
    res = requests.get(url).json()
    # print(res)

    return res["result"]

def get_info_from_google_api(latitude, longitude):
    """This function takes in a latitude and a longitude, queris
    the google places API, then returns a list of places around current location.

    Args:
        latitude (string): Current user's latitude
        longitude (string): Currrent user's longitude

    Returns:
        [{obj}]: Returns a list of places around current user's location
    """

    types = ["bar", "cafe", "restaurant"]
    final_ret = []

    for type in types:

        # Building the base url
        url = f"{NEARBY_URL}location={latitude},{longitude}&radius={2400}&type={type}&key={API_KEY}"
        print(url)

        # Making a request to google places api
        res = requests.get(url).json()
        print(f"{len(res['results'])} places found")

        final_ret.extend(res["results"])

    return final_ret

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

def updatePlacesFromApis(geohashes):
    """This function queries the places from our database that
    need to be updated and then updates them using the external
    APIs.

    Args:
        geohashes ([hashes]): List of geohashes to update
    """

    # Query the places to update
    old_places = dynamodb.fetchPlacesFromDatabase(geohashes)
    new_places = []

    for place in old_places:

        address = f"({place['name']}) {place['address']}"
        to_add = livepopulartimes.get_populartimes_by_address(address)
        new_places.append(to_add)
    
    print(new_places)

    return new_places

def getPhotosFromGoogleApi(photos):
    """This function loops through the photos element returned
    by google place detail api, and create images from there

    Args:
        photos (list of photos): List of photos elements
    """
    index = 1
    for photo in photos:
        ref = photo["photo_reference"]
        url = f"https://maps.googleapis.com/maps/api/place/photo?photo_reference={ref}&key={API_KEY}"

        res_d = requests.get(url)

        with open(f"image_{index}.jpeg", "wb") as f:
            for chunk in res_d:
                if chunk:
                    f.write(chunk)

        index += 1

def addExtraInfoToPlaces(places):
    """This function adds the website, phone number, and other informations
    to the place information.

    Args:
        places ([dict]): List of places that we need to complete
    """

    new_places = []
    print(f"Will update {len(places)}")
    for place in places:
        ret = get_place_info_from_google(place["place_id"])

        place["phone_number"] = ret["international_phone_number"] if "international_phone_number" in ret else ret["phone_number"] if "phone_number" in ret else ""
        place["website"] = ret["website"] if "website" in ret else ""
        place["price_level"] = ret["price_level"] if "price_level" in ret else ""
        place["photos"] = ret["photos"] if "photos" in ret else []
        place["reviews"] = ret["reviews"] if "reviews" in ret else []

        new_places.append(place)
    
    return new_places

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

    final_places = addExtraInfoToPlaces(final_places)

    # And we return all places
    return final_places

if __name__ == "__main__":
    # fetchPlacesFromApis(["u09w5", "u09t7"])
    get_place_info_from_google("ChIJieGyj-HHwoARK-hwrwbi76E")