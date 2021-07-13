import json
from utils.get_geohashes_in_radius import getGeohashesInRadius
from utils.dynamodb_handler import getGeohashesStatus

def nearby(event, context):

    body = json.loads(event['body'])
    
    hashes = getGeohashesInRadius(float(body["latitude"]), float(body["longitude"]), 10)

    items = getGeohashesStatus(hashes["five_digits"])

    response = {
        "statusCode": 200,
        "body": json.dumps(items)
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
