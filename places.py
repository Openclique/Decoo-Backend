import json
from utils import functions, dynamodb

def nearby(event, context):

    body = json.loads(event['body'])
    places = []

    # We get a list of all geohashes in the user's radius
    hashes = functions.getGeohashesInRadius(float(body["latitude"]), float(body["longitude"]), 10)

    # Then we check which geohashes need to be updated
    items = dynamodb.getGeohashesStatus(hashes["five_digits"])

    print(items)

    # We then fetch informations for all geohashes that need to be updated
    places += functions.fetchPlacesFromApis(items["to_update"])

    # We save these informations on our database
    dynamodb.batchUpdatePlaces(places)

    # And we query the ones that were already up to date
    places += dynamodb.fetchPlacesFromDatabase(items["up_to_date"])

    print(places)

    response = {
        "statusCode": 200,
        "body": json.dumps(places)
    }

    return response

    # Use this code if you don't use the http event with the LAMBDA-PROXY
    # integration
    """
    return {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "event": event
    }
    """
