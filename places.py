import json
from utils import functions, dynamodb
from decimal import Decimal

RADIUS = 5

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
        places = functions.fetchPlacesFromApis(both_hashes)
    else:
        places = []
        # If there is any new hashes we still need to build a database for it
        if len(new_hashes) > 0:
            places.extend(functions.fetchPlacesFromApis(new_hashes))

        # And we simply update the hashes that already existed
        places.extend(functions.updatePlacesFromApis(old_hashes))

    final_places = []
    for place in places:
        if place not in final_places:
            final_places.append(place)

    print(f"{len(final_places)} will be updated")

    # And we save the places in the database
    dynamodb.batchUpdatePlaces(final_places, get_new_points=get_new_points)

    # And finally we update dynamodb to remember that these hashes have been updated
    dynamodb.rememberHashesUpdate(both_hashes)

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
        dynamodb.rememberCurrentQuery(hashes["five_digits"])

        # Then we check which geohashes need to be created
        items = dynamodb.getGeohashesStatus(hashes["five_digits"])

        # We then fetch informations for all geohashes that need to be updated
        # places = functions.fetchPlacesFromApis(items["to_update"])

        # We query the places from database
        places = dynamodb.fetchPlacesFromDatabase(items["up_to_date"])

        response = {
            "statusCode": 200,
            "body": json.dumps(places, default=functions.decimal_serializer)
        }

        return response
    
    # print(nearby_test(40.8558834, 2.3814812))
    updater({}, {})