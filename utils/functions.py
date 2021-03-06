import numpy
import math
import livepopulartimes
import requests
import os
from geolib import geohash
from decimal import Decimal
import math
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz
import time
import boto3
from botocore.exceptions import NoCredentialsError
# import safegraphql.client as sgql

from utils import dynamodb

NEARBY_URL = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
DETAIL_URL = f"https://maps.googleapis.com/maps/api/place/details/json?"
TYPE = "bar"
RADIUS=5000
GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")
BEST_TIMES_API_KEY=os.getenv("BEST_TIMES_API_KEY")
AWS_ACCESS_KEY=os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY=os.getenv("AWS_SECRET_KEY")
SAFEGRAPH_API_KEY=os.getenv("SAFEGRAPH_API_KEY")
BAR_KEYWORDS = ['bar', 'bistro', 'cafe']
PUB_KEYWORDS = ['pub', 'brewery', 'lounge', 'beer']
CLUB_KEYWORDS = ['club']
BLACKLISTED_KEYWORDS = ['restaurant', 'store', 'tabac', 'pmu', 'shop', 'newsstand', 'bakery', 'tea house', 'espresso', 'lottery retailer', 'wholesaler', 'printer', 'fitness', 'school', 'dance', 'grill', 'sports', 'futsal', 'park', 'soccer', 'market', 'hypermarket', 'field', 'press', 'bank', 'atm', 'patisserie', 'supermarket', 'pool']

LIMIT=100
VERSION = "20180604"
CLIENT_ID = "5ZHWR3EUGRQR3GEBKMRMNIOPRIC1BFIJKFNWHBTJPU3BLRSJ"
CLIENT_SECRET = "3ASIOGMFANYYKE5OGNYBGQ3QZ02SS2NOEMMIFVQIQYTPFMEU"

class number_str(float):
    def __init__(self, o):
        self.o = o
    def __repr__(self):
        return str(self.o)

def decimal_serializer(o):
    if isinstance(o, Decimal):
        return number_str(o)
    raise TypeError(repr(o) + " is not JSON serializable")

def custom_next(my_list):
    try:
        return next(i for i in range(len(my_list)) if my_list[i] != 0 and i >= 4)
    except Exception:
        return -1
    
def custom_reversed_next(my_list):
    try:
        value = next(i for i in reversed(range(len(my_list))) if my_list[i] != 0)
        if value == 23:
            custom_next()
        return value
    except Exception:
        return -1

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
    lon2 = math.fmod(lon2 + 3*math.pi, 2*math.pi) - math.pi  # normalise to -180..+180??
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

    url = f"{DETAIL_URL}place_id={place_id}&key={GOOGLE_API_KEY}"
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

    types = ["bar", "night_club"]
    final_ret = []

    for type in types:

        to_add = []
        
        # Building the base url
        url = f"{NEARBY_URL}location={latitude},{longitude}&radius={2400}&type={type}&key={GOOGLE_API_KEY}"
        print(url)

        while True:

            # Making a request to google places api
            res = requests.get(url).json()

            to_add.extend(res["results"])
            print(res.keys())
            print(len(res["results"]))
            if not "next_page_token" in res.keys():
                break

            url = f"{NEARBY_URL}location={latitude},{longitude}&radius={2400}&type={type}&key={GOOGLE_API_KEY}&pagetoken={res['next_page_token']}"

            time.sleep(2)
        
        print(f"{len(to_add)} places have been found for {type}s")

        final_ret.extend(to_add)

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
        try:
            to_add = livepopulartimes.get_populartimes_by_address(address)
        except Exception as err:
            print("error happened")
            print(err)
            to_add = {}

        success = False

        # If we couldn't find the proper informations for this place, we try to get it from best times
        if not to_add['coordinates'] or not to_add['popular_times'] or not to_add["populartimes"]:
            print("\nCouldn't find informations on google, trying best times")
            # print("GOOGLE'S INFO:")
            # print(to_add)
            # forecast = searchVenueFromBestTimes(to_add)
            # print("BEST TIMES INFO:")
            # print(forecast)
            # to_add, success = buildPlaceInfoFromBestTime(to_add)
            # print("Place after best time info:")
            # print(to_add)
        else:
            success = True
            to_add["has_current_popularity"] = True if to_add["current_popularity"] else False
            to_add["current_popularity"] = 1 if not to_add["current_popularity"] else to_add["current_popularity"]

        if success:
            places.append(to_add)

    # And we return these informations
    return places

def updatePlacesFromApis(geohashes, get_new_points):
    """This function queries the places from our database that
    need to be updated and then updates them using the external
    APIs.

    Args:
        geohashes ([hashes]): List of geohashes to update
    """

    # Query the places to update
    old_places = dynamodb.fetchPlacesFromDatabase(geohashes)
    new_places = []
    hashes_updated = []
    index = 0

    for place in old_places:

        if not place["has_current_popularity"] or not isPlaceOpen(place, 0.0, use_epoch=False):
            continue

        if place['id'] not in hashes_updated:
            hashes_updated.append(place['id'])

        index += 1

        success = False
        address = f"({place['name']}) {place['address']}"
        to_add = livepopulartimes.get_populartimes_by_address(address)

        # If we couldn't find the proper informations for this place, we try to get it from best times
        if not to_add['coordinates'] or not to_add['popular_times'] or not to_add["current_popularity"]:
            print("Coudln't get info from popular times")
            # place, success = buildPlaceInfoFromBestTime(place, update=True)
        else:
            place["current_popularity"] = to_add["current_popularity"]
            success = True

        if success:
            new_places.append(place)
        
        # Every 50 place we update the database
        if index % 50 == 0:

            # We remove duplicate places
            final_places = []
            final_places_ids = []
            for place in new_places:
                if place not in final_places and no_blacklisted_words(place["categories"]) and place["place_id"] not in final_places_ids:
                    final_places.append(place)
                    final_places_ids.append(place["place_id"])
            dynamodb.batchUpdatePlaces(final_places, get_new_points=get_new_points)

            # And finally we update dynamodb to remember that these hashes have been updated
            dynamodb.rememberHashesUpdate(hashes_updated)

            new_places = []
    
    # We remove duplicate places
    final_places = []
    final_places_ids = []
    for place in new_places:
        if place not in final_places and no_blacklisted_words(place["categories"]) and place["place_id"] not in final_places_ids:
            final_places.append(place)
            final_places_ids.append(place["place_id"])

    dynamodb.batchUpdatePlaces(final_places, get_new_points=get_new_points)

    # And finally we update dynamodb to remember that these hashes have been updated
    dynamodb.rememberHashesUpdate(hashes_updated)

    return True

def upload_file(remote_url, bucket, file_name):
    s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
    try:
        imageResponse = requests.get(remote_url, stream=True).raw
        s3.upload_fileobj(imageResponse, bucket, f"{file_name}.png", ExtraArgs={'ACL':'public-read'})
        print("Upload Successful")
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False

def uploadPhotosFromGoogleApi(photos, place):
    """This function loops through the photos element returned
    by google place detail api, and create images from there

    Args:
        photos (list of photos): List of photos elements
        place (google place): place informations
    
    Returns:
        photos: List of photos with aws s3 url added
    """
    index = 1
    for photo in photos:
        ref = photo["photo_reference"]
        url = f"https://maps.googleapis.com/maps/api/place/photo?photo_reference={ref}&key={GOOGLE_API_KEY}"
        is_success = upload_file(url, "mappn-images", f"{place['place_id']}/image_{index}")

        if is_success:
            photo["url"] = f"http://s3-us-west-1.amazonaws.com/mappn-images/{place['place_id']}/image_{index}.png"
            
        index += 1
    
    return photos

def createOpenHours(populartimes):
    """This function creates the open hours object
    from the populartimes informationss

    Args:
        populartimes (array): populartimes from livepopulartimes python library

    Returns:
        List of objects
    """
    to_ret = []
    for time in populartimes:
        skip = False
        to_add = {}
        if time[1]:
            for x in time[1]:
                if x[1] > 0 and not skip:
                    to_add["open"] = x[0]
                    skip = True
            to_add["close"] = time[1][-1][0] + 1
            to_ret.append(to_add)
        else:
            to_ret.append({})

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    final = []
    index = 0
    skipped = False
    for info in to_ret:
        if index == 0 and not skipped:
            skipped = True
        else:
            final.append({
                "day": days[index],
                "hour_close": info["close"] if "close" in info else -1,
                "hour_open": info["open"] if "open" in info else -1
            })
            index += 1

    final.append({
        "day": days[index],
        "hour_close": to_ret[0]["close"] if "close" in to_ret[0] else -1,
        "hour_open": to_ret[0]["open"] if "open" in to_ret[0] else -1
    })

    return final

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

        # If there is some photos we store them in aws s3
        if "photos" in ret:
            # photos_to_add = uploadPhotosFromGoogleApi(ret["photos"], ret)
            # place["photos"] = photos_to_add
            place["photos"] = ret["photos"]
        else:
            place["photos"] = []

        place["reviews"] = ret["reviews"] if "reviews" in ret else []
        place["open_hours"] = createOpenHours(place["popular_times"])
        place["type"] = getType(place)

        new_places.append(place)
    
    return new_places

def getType(place):
    """[summary]

    Args:
        place ([type]): [description]
    """
    for word in CLUB_KEYWORDS:
        for category in place["categories"]:
            if word.lower() in category.lower():
                return "Club"
    for word in PUB_KEYWORDS:
        for category in place["categories"]:
            if word.lower() in category.lower():
                return "Pub"
    for word in BAR_KEYWORDS:
        for category in place["categories"]:
            if word.lower() in category.lower():
                return "Bar"
    return "none"

def no_blacklisted_words(categories):
    for word in BLACKLISTED_KEYWORDS:
        for category in categories:
            if word.lower() in category.lower():
                return False
    return True

def fetchPlacesFromApis(geohashes, get_new_points):
    '''
    This function takes in a list of geohashes and queries informations from external APIs
    to put in our database
    :geohashes: ([str]) A list of 5 digits geohashes that we need to update
    Returns:
    :places: ([str]) A list of places informations
    '''

    # We loop through all geohashes
    for geo in geohashes:

        # First we convert the geohash to lat lon
        coords = geohash.decode(geo)

        # Then we fetch the APIs to get places around this location
        places = get_places_around_location(coords.lat,coords.lon)

        # Removing duplicates
        intermediate_places = []
        intermediate_places_ids = []
        for place in places:
            if place not in intermediate_places and no_blacklisted_words(place["categories"]) and place["place_id"] not in intermediate_places_ids:
                intermediate_places.append(place)
                intermediate_places_ids.append(place["place_id"])
        
        # Add some infos
        intermediate_places = addExtraInfoToPlaces(intermediate_places)

        # Removing duplicates again just to be sure
        final_places = []
        final_places_ids = []
        for place in intermediate_places:
            if place not in final_places and no_blacklisted_words(place["categories"]) and place["place_id"] not in final_places_ids:
                final_places.append(place)
                final_places_ids.append(place["place_id"])

        # Then update places
        dynamodb.batchUpdatePlaces(final_places, get_new_points=get_new_points)

        # And finally we update dynamodb to remember that this hash has been updated
        dynamodb.rememberHashesUpdate([geo])

    return True

def buildPlaceInfoFromBestTime(place, update=False):
    """[summary]

    Args:
        place ([type]): [description]
    """

    # We get the forecast and live info for current place
    live_info = getLiveFromBestTimes(place)

    if "analysis" not in live_info or not live_info["analysis"]["venue_live_busyness_available"]:
        return {}, False

    # If we are fetching this point for the first time, we queyr all informations
    if not update:
        forecast_info = getForecastFromBestTimes(place)
        
        # Then we create our informations using it
        place["current_popularity"] = live_info["analysis"]["venue_live_busyness"]
        place["populartimes"] = [
            {
                "name": x['day_info']['day_text'],
                "data": x['day_raw'],
                'busy_hours': x["busy_hours"],
                'quiet_hours': x["quiet_hours"],
                'peak_hours': x["peak_hours"],
                'surge_hours': x["surge_hours"],
            } for x in forecast_info["analysis"]
        ]
        place["popular_times"] = []
        place["time_spent"] = forecast_info["venu_info"]["venue_dwell_time_avg"]
    
    # Otherwise we simply query current live traffic
    else:
        place["current_popularity"] = live_info["analysis"]["venue_live_busyness"]

    return place, True

def searchPlacesBySafeGraph(city):
    """[summary]
    """
    sgql_client = sgql.HTTP_Client(apikey=SAFEGRAPH_API_KEY)

    naics = 722410
    cols = [
        'location_name',
        'street_address',
        'city',
        'latitude',
        'longitude',
        'region',
        'brands',
        'raw_visit_counts',
        'visits_by_day',
        'distance_from_home',
        'median_dwell',
        'related_same_day_brand',
        'related_same_month_brand',
        'popularity_by_hour',
        'device_type'
    ]

    ret = sgql_client.search(product = 'monthly_patterns', date = '2021-07-06', city = city, naics_code = naics, columns = cols, max_results = 5)

    return ret

def exploreSearchByFoursquare(latitude, longitude):
    """[summary]
    """
    url = f"https://api.foursquare.com/v2/venues/explore?&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&v={VERSION}&ll={latitude},{longitude}&radius={RADIUS}&limit={LIMIT}"
    results = requests.get(url).json()["response"]['groups'][0]['items']

    return results

def getVenueDetailsbyFoursquare(venue_id):
    """[summary]

    Args:
        venue_id ([type]): [description]
    """
    url = f"https://api.foursquare.com/v2/venues/{venue_id}?&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&v={VERSION}"

    ret = requests.get(url).json()["response"]["venue"]

    return ret

def getVenueHoursByFoursquare(venue_id):
    """[summary]

    Args:
        venue_id ([type]): [description]
    """
    url = f"https://api.foursquare.com/v2/venues/{venue_id}/hours?&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&v={VERSION}"

    ret = requests.get(url).json()

    return ret

def getVenueEventsByFoursquare(venue_id):
    """[summary]

    Args:
        venue_id ([type]): [description]
    """
    url = f"https://api.foursquare.com/v2/venues/{venue_id}/events?&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&v={VERSION}"

    ret = requests.get(url).json()

    return ret

def searchVenueFromBestTimes(place):
    """[summary]
    TODO: Use this endpoint on each place to get extra informations about a place

    Args:
        place ([type]): [description]
    """
    url = "https://besttime.app/api/v1/venues/search"

    params = {
        'api_key_private': BEST_TIMES_API_KEY,
        'q': f'{place["name"]} {place["address"]}'
    }

    ret = requests.request("POST", url, params=params).json()

    return ret

def getForecastFromBestTimes(place):
    """[summary]
    TODO: Use this endpoint on each place to get extra informations about a place

    Args:
        place ([type]): [description]
    """
    url = "https://besttime.app/api/v1/forecasts"

    params = {
        'api_key_private': BEST_TIMES_API_KEY,
        'venue_name': place["name"],
        'venue_address': place["address"]
    }

    ret = requests.request("POST", url, params=params).json()

    # venu_info
    # {
    #     'venue_id': 'ven_3045523979346c3373336852636b3547755f5f495664774a496843',
    #     'venue_name': 'Franprix',
    #     'venue_address': '6 R??sidence Parc Montaigne 78330 Fontenay-le-Fleury France',
    #     'venue_timezone': 'Europe/Paris',
    #     'venue_dwell_time_min': 20,
    #     'venue_dwell_time_max': 20,
    #     'venue_dwell_time_avg': 20,
    #     'venue_type': 'SUPERMARKET',
    #     'venue_types': ['supermarket', 'fast_food_restaurant', 'grocery_store', 'organic_restaurant'],
    #     'venue_lat': 48.814026999999996,
    #     'venue_lon': 2.0523918
    # }

    # analysis
    # {
    #     'day_info': {
    #         'day_int': 0,
    #         'day_text': 'Monday',
    #         'venue_open': 0,
    #         'venue_closed': 0,
    #         'day_rank_mean': 7,
    #         'day_rank_max': 7,
    #         'day_mean': 16,
    #         'day_max': 39
    #     },
    #     'busy_hours': [19, 20],
    #     'quiet_hours': [6, 7, 8, 9, 10, 0, 1, 2, 3, 4, 5],
    #     'peak_hours': [{'peak_start': 12, 'peak_max': 19, 'peak_end': 22, 'peak_intensity': 2, 'peak_delta_mean_week': 17}],
    #     'surge_hours': {'most_people_come': 12, 'most_people_leave': 22},
    #     'hour_analysis': [{'hour': 6, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 7, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 8, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 9, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 10, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 11, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 12, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 13, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 14, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 15, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 16, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 17, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 18, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 19, 'intensity_txt': 'Above average', 'intensity_nr': 1}, {'hour': 20, 'intensity_txt': 'Above average', 'intensity_nr': 1}, {'hour': 21, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 22, 'intensity_txt': 'Average', 'intensity_nr': 0}, {'hour': 23, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 0, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 1, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 2, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 3, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 4, 'intensity_txt': 'Low', 'intensity_nr': -2}, {'hour': 5, 'intensity_txt': 'Low', 'intensity_nr': -2}],
    #     'day_raw': [0, 0, 0, 5, 5, 10, 20, 25, 30, 35, 35, 35, 35, 40, 40, 30, 20, 10, 5, 0, 0, 0, 0, 0]
    # }

    return ret

def getLiveFromBestTimes(place):
    """[summary]

    Args:
        place ([type]): [description]
    """
    url = "https://besttime.app/api/v1/forecasts/live"

    params = {
        'api_key_private': BEST_TIMES_API_KEY,
        'venue_name': place["name"],
        'venue_address': place["address"]
    }

    print(params)

    ret = requests.request("POST", url, params=params).json()

    # {
    #     'status': 'OK',
    #     'analysis': {
    #         'venue_forecasted_busyness': 90,
    #         'venue_forecasted_busyness_available': True,
    #         'venue_live_busyness': 75,
    #         'venue_live_busyness_available': True,
    #         'venue_live_forecasted_delta': -15,
    #         'hour_start': 19,
    #         'hour_start_12': '7PM',
    #         'hour_end': 20,
    #         'hour_end_12': '8PM'
    #     },
    #     'venue_info': {
    #         'venue_current_gmttime': 'Saturday 2021-11-20 06:26PM',
    #         'venue_current_localtime': 'Saturday 2021-11-20 07:26PM',
    #         'venue_id': 'ven_496b5f312d37394568697752636b35474f74456e3336714a496843',
    #         'venue_name': 'UGC',
    #         'venue_address': '1 Av. de la Source de la Bi??vre 78180 Montigny-le-Bretonneux France',
    #         'venue_timezone': 'Europe/Paris',
    #         'venue_open': 'Open',
    #         'venue_dwell_time_min': 0,
    #         'venue_dwell_time_max': 0,
    #         'venue_dwell_time_avg': 0,
    #         'venue_lat': 48.784072699999996,
    #         'venue_lon': 2.0409398
    #     }
    # }

    return ret

def getNearbyFromBestTime(lat, lng):
    """[summary]

    Args:
        place ([type]): [description]
    """
    url = "https://besttime.app/api/v1/venues/filter"
    params = {
        'api_key_private': BEST_TIMES_API_KEY,
        # 'busy_min': 50,
        # 'busy_max': 100,
        # 'hour_min': 18,
        # 'hour_max': 23,
        # 'busy_conf':'any',
        'types': ['BAR','CAFE','RESTAURANT', 'CLUBS'],
        'lat': lat,
        'lng': lng,
        'radius': 2000,
        # 'order_by': ['day_rank_max','reviews'],
        # 'order': ['desc','desc'],
        'foot_traffic': 'both',
        # 'limit': 20,
        # 'page': 0
    }
    response = requests.request("GET", url, params=params)
    print(response.json())

def addInfoToReturnedPlaces(places, user_latitude, user_longitude, latitude, longitude, epoch):
    """
    This function adds the distance, the photos, and the open now bool

    TODO: Query place photos before returning informations
    Args:
        places (list): List of places to complete
    """
    new_places = []

    for place in places:
        place["open_now"] = isPlaceOpen(place, epoch, use_epoch=True)
        place["distance"] = distance((user_latitude, user_longitude), (float(place["coordinates"]["lat"]), float(place["coordinates"]["lng"])))
        place["distance_from_query"] = distance((latitude, longitude), (float(place["coordinates"]["lat"]), float(place["coordinates"]["lng"])))

        new_places.append(place)
    
    return new_places

def isPlaceOpen(place, epoch, use_epoch=False):
    """[summary]

    Args:
        place ([type]): [description]
        epoch (float): [description]
    """

    latitude = place["coordinates"]["lat"]
    longitude = place["coordinates"]["lng"]

    if not use_epoch:
        zone = TimezoneFinder().timezone_at(lng=longitude, lat=latitude)
        current_hour = datetime.now(pytz.timezone(zone)).hour
        current_day_of_week = datetime.now(pytz.timezone(zone)).weekday()

    else:
        current_hour = datetime.fromtimestamp(epoch).hour
        current_day_of_week = datetime.fromtimestamp(epoch).weekday()

    ret = (place["open_hours"][current_day_of_week]["hour_open"] <= current_hour < place["open_hours"][current_day_of_week]["hour_close"])

    return ret

def distance(origin, destination):
    """
    Calculate the Haversine distance.

    Args
        origin : tuple of float (lat, long)
        destination : tuple of float (lat, long)

    Returns:
        distance_in_km : float

    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = radius * c

    return d

if __name__ == "__main__":
    places = fetchPlacesFromApis(["u09mw"])
    # for place in places:
    #     getForecastFromBestTimes(place)
    #     getLiveFromBestTimes(place)
    # get_place_info_from_google("ChIJieGyj-HHwoARK-hwrwbi76E")