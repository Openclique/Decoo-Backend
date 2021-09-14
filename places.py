import json
from utils import functions, dynamodb

RADIUS = 10

def all(event, context):
    """
    This function returns all our points of interest with a current_popularity not null
    """
    places = dynamodb.fetchAllPlacesFromDatabase()

    response = {
        "statusCode": 200,
        "body": json.dumps(places)
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

    # Then we check which geohashes need to be created
    items = dynamodb.getGeohashesStatus(hashes["five_digits"])

    print(items)

    # We then fetch informations for all geohashes that need to be updated
    places = functions.fetchPlacesFromApis(items["to_update"])

    # We query the places from database
    places += dynamodb.fetchPlacesFromDatabase(items["up_to_date"])

    print(places)

    response = {
        "statusCode": 200,
        "body": json.dumps(places)
    }

    return response

def updater(event, context):
    '''
    This function is called on a cronjob every X minutes.
    It looks at the geohashes that have been queried in the last 15 minutes
    and updates them.
    '''

    # We get a list of all geohashes that need to be updated in the database
    hashes = dynamodb.getGeohashesThatNeedToBeUpdated()

    # We then fetch informations for all geohashes that need to be updated
    places = functions.fetchPlacesFromApis(hashes)

    response = {
        "statusCode": 200,
        "body": json.dumps({"message": "Success"})
    }

    return response