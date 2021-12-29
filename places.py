import json
from utils import functions, dynamodb
from decimal import Decimal

RADIUS = 5 # km

def all(event, context):
    """
    This function returns all our points of interest with a current_popularity not null
    """
    places = dynamodb.fetchAllPlacesFromDatabase("places-prod")

    print(places)

    response = {
        "statusCode": 200,
        "body": json.dumps(places, parse_float=Decimal)
    }

    return response

def nearby(event, context):
    '''
    This function is called by the frontend when the user fetches the
    places around him.
    '''

    body = json.loads(event['body'])
    places = []

    # We get a list of all geohashes in the user's radius
    hashes = functions.getGeohashesInRadius(float(body["latitude"]), float(body["longitude"]), RADIUS)

    # We remember that this area has been queried for the updating cron job
    dynamodb.rememberCurrentQuery(hashes["five_digits"])

    # Then we check which geohashes need to be created
    items = dynamodb.getGeohashesStatus(hashes["five_digits"])

    to_fetch = items["up_to_date"]
    to_fetch.extend(items["to_update"])

    # We query the places from database
    places = dynamodb.fetchPlacesFromDatabase(to_fetch)

    places = functions.addInfoToReturnedPlaces(places, float(body["user_latitude"]), float(body["user_longitude"]), float(body["epoch"]))

    places = sorted(places, key=lambda place: place["distance"])

    response = {
        "statusCode": 200,
        "body": json.dumps(places, default=functions.decimal_serializer)
    }

    return response

def updater(event, context):
    '''
    This function is called on a cronjob every X minutes.
    It looks at the geohashes that have been queried in the last 15 minutes
    and updates them.

    TODO: Split updating into multiple threads for it not to take 10 minutes
    '''

    # We get a list of all geohashes that need to be updated in the database
    ret = dynamodb.getGeohashesThatNeedToBeUpdated()

    new_hashes = [x[0] for x in ret if x[1]]
    old_hashes = [x[0] for x in ret if not x[1]]
    both_hashes = [x[0] for x in ret]

    print(f"{len(new_hashes) + len(old_hashes)} hashes will be updated")
    
    get_new_points = dynamodb.shouldFetchNewPlaces()

    print(f"Will get new points: {get_new_points}")

    # Every 24 hours we try to get new places from external apis to keeep
    # increasing our database
    if get_new_points:
        functions.fetchPlacesFromApis(both_hashes, get_new_points)
    else:
        places = []
        # If there is any new hashes we still need to build a database for it
        if len(new_hashes) > 0:
            functions.fetchPlacesFromApis(new_hashes, get_new_points)

        # And we simply update the hashes that already existed
        functions.updatePlacesFromApis(old_hashes, get_new_points)

    response = {
        "statusCode": 200,
        "body": json.dumps({"message": "Success"})
    }

    return response

if __name__ == "__main__":

    def nearby_test(latitude=0.0, longitude=0.0):
        '''
        This function is called by the frontend when the user fetches the
        places around him.
        '''


        places = []

        # We get a list of all geohashes in the user's radius
        hashes = functions.getGeohashesInRadius(float(latitude), float(longitude), RADIUS)
        print(hashes)

        # We remember that this area has been queried for the updating cron job
        # dynamodb.rememberCurrentQuery(hashes["five_digits"])

        # Then we check which geohashes need to be created
        items = dynamodb.getGeohashesStatus(hashes["five_digits"])

        to_fetch = items["up_to_date"]
        to_fetch.extend(items["to_update"])

        # We query the places from database
        places = dynamodb.fetchPlacesFromDatabase(to_fetch)

        places = functions.addInfoToReturnedPlaces(places, latitude, longitude, 0.0)

        return places
    
    # print(nearby_test(48.866667, 2.333333))
    # updater({}, {})
    # res = functions.get_place_info_from_google("ChIJieGyj-HHwoARK-hwrwbi76E")
    # print(res.keys())
    # print(res["international_phone_number"])
    # print(res["website"])
    # print(res["price_level"])
    # print(res["photos"])
    # print(res["reviews"])

    # GETTING PHOTOS FROM GOOGLE API
    # TODO: HOW TO SAVE THE IMAGES ?
    # functions.getPhotosFromGoogleApi(res["photos"])

    # ADD EXTRA INFO TO ALL CURRENT PLACES
    places = dynamodb.fetchAllPlacesFromDatabase("places-prod")
    keywords = []
    for place in places:
        for category in place["categories"]:
            if category not in keywords:
                keywords.append(category)
    print(keywords)
    # i = 1
    # for place in places:
    #     print(i)
    #     if len(place["populartimes"]) > 0 and "name" in place["populartimes"][0].keys() and "data" in place["populartimes"][0].keys():
    #         i += 1
    #         place["open_hours"] = [
    #             {
    #                 "day": x["name"],
    #                 "hour_open": functions.custom_next(x["data"]) + 1,
    #                 "hour_close": functions.custom_reversed_next(x["data"]) + 1
    #             }
    #             for x in place["populartimes"]
    #         ]
    # start_index = 0
    # stop_index = 0
    # while stop_index < len(places):
    #     stop_index += 50
    #     if stop_index > len(places):
    #         stop_index = len(places)
    #     print(f"Updating from {start_index} to {stop_index}")
    #     dynamodb.batchUpdatePlaces(places[start_index:stop_index])
    #     start_index = stop_index

    # TEST BEST TIME API IN A GEOHASH LIST
    # places = dynamodb.fetchPlacesFromDatabase(["u09mw"])
    # # print(places)
    # for place in places:
    #     place_forecast = functions.getForecastFromBestTimes(place)
    #     place_live = functions.getLiveFromBestTimes(place)
    #     print(place_live)

    # TEST BEST TIME NEARBY API
    # functions.getNearbyFromBestTime(51.5121172,-0.126173)

    # TEST GETTING PLACES FROM EXTERNALf API FOR GEOHASH LIST
    # hashes = functions.getGeohashesInRadius(34.0395553,-118.2633982,5)
    # print(hashes["five_digits"])
    # places = functions.fetchPlacesFromApis(hashes["five_digits"])
    # final_places = []
    # for place in places:
    #     if place not in final_places:
    #         final_places.append(place)

    # print(f"{len(final_places)} will be updated")

    # # And we save the places in the database
    # dynamodb.batchUpdatePlaces(final_places)

    # places = functions.get_info_from_google_api(34.0395553,-118.2633982)
    # print(len(places))

    # open_hours = [
    #     {
    #         "day": "Monday",
    #         "hour_close": 14,
    #         "hour_open": 9
    #     },
    #     {
    #     "day": "Tuesday",
    #     "hour_close": 14,
    #     "hour_open": 9
    #     },
    #     {
    #     "day": "Wednesday",
    #     "hour_close": 22,
    #     "hour_open": 5
    #     },
    #     {
    #     "day": "Thursday",
    #     "hour_close": 0,
    #     "hour_open": 0
    #     },
    #     {
    #     "day": "Friday",
    #     "hour_close": 14,
    #     "hour_open": 9
    #     },
    #     {
    #     "day": "Saturday",
    #     "hour_close": 14,
    #     "hour_open": 9
    #     },
    #     {
    #     "day": "Sunday",
    #     "hour_close": 14,
    #     "hour_open": 9
    #     }
    # ]
    # coordinates = {
    #     "lng": 2.333333,
    #     "lat": 48.866667
    # }
    # place = {
    #     "open_hours": open_hours,
    #     "coordinates": coordinates
    # }
    # functions.isPlaceOpen(place)
    