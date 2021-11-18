import json
from utils import functions, dynamodb
from decimal import Decimal

RADIUS = 10

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

    # We query the places from database
    places = dynamodb.fetchPlacesFromDatabase(items["up_to_date"])

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
    '''

    # We get a list of all geohashes that need to be updated in the database
    hashes = dynamodb.getGeohashesThatNeedToBeUpdated()

    print(hashes)
    
    # We then fetch informations for all geohashes that need to be updated
    places = functions.fetchPlacesFromApis(hashes)

    print(f"{len(places)} will be updated")

    # And we save the places in the database
    dynamodb.batchUpdatePlaces(places)

    # And finally we update dynamodb to remember that these hashes have been updated
    dynamodb.rememberHashesUpdate(hashes)

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
    
    print(nearby_test(48.855854, 2.381733))
    # updater({}, {})