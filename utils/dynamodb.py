import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from datetime import datetime
from geolib import geohash
from decimal import Decimal
import json

dynamodb = boto3.resource('dynamodb')
PLACES_TABLE = "places-dev"
GEOHASHES_TABLE = "geohashes-dev"

def isUpToDate(dynamodb_hash):
    '''
    This function takes in a geohash element from the dynamodb table
    and checks if it is up to date (updated in the last 15 min)
    '''
    current_timestamp = int(datetime.now().timestamp())
    hash_last_update = dynamodb_hash["last_update"]

    # If the hash zone has not been updated in the last 900 seconds (15 min)
    if current_timestamp - hash_last_update > 900:
        return False

    return True

def getGeohashesStatus(geohashes):
    '''
    This function takes in a list of geohashes and checks if they have been updated
    recently
    :geohashes: ([str]) List of 5 digits geohashes to look for
    Returns:
    :ret: (object) Object holding informations about which geohashes are up to date,
                   and which need to be updated
    '''

    ret = {
        "to_update": [],
        "up_to_date": []
    }

    response, error = batchGetItems(GEOHASHES_TABLE, keys=geohashes)
    
    # We extract the informations we found in database 
    found_hashes = response["Responses"]["geohashes-dev"]

    # We then create the return object
    ret["up_to_date"] = [h["geohash"] for h in found_hashes if isUpToDate(h)]
    ret["to_update"] = [h for h in geohashes if h not in ret["up_to_date"]]
    ret["error"] = error

    return ret

def batchUpdatePlaces(places=[]):
    '''
    This function takes in a list of places informations and add them into
    our database
    :places: ([object]) list of places informations queried from external APIs
    Returns:
    :bool: True if success, False if error
    '''

    print("Running batch update")
    with dynamodb.Table("places-prod").batch_writer() as batch:

        # We loop through each place
        for place in places:

            # If the place doesn't have coordinates we simply skip it
            if not place['coordinates'] or not place['popular_times']:
                continue

            # We convert lat, lon to 5 and 10 digits geohashes
            ten_digits_hash = geohash.encode(place['coordinates']["lat"], place['coordinates']["lng"], 10)
            five_digits_hash = ten_digits_hash[:5]
            place["id"] = five_digits_hash
            place["geohash"] = ten_digits_hash

            # Then we update the geohashes table
            print("Place after adding geohash")
            print(place)

            ddb_data = json.loads(json.dumps(place), parse_float=Decimal)

            # Then we update the places table
            batch.put_item(Item=ddb_data)

    
    return True

def batchGetItems(table, keys=[], sortKeys=[]):
    '''
    This function takes in a table name and a list of keys or sort keys, and returns
    all the items that are matching the pattern
    :table: (str) name of the dynamodb table to query
    :keys: (str) unique identifiers to query in table
    :sortKeys: (str) identifiers to look for in table
    '''

    error = False
    response = {}

    # We create the request body required by boto3.dynamodb.batch_get_item
    request = {
        table: {
            'Keys': []
        }
    }
    for geohash in keys:
        request[table]['Keys'].append({
            "geohash": geohash
        })
    
    # Then we batch get the dynamodb table
    try:
        response = dynamodb.batch_get_item(
            RequestItems=request,
        )
    except Exception as e:
        error = True
    
    return response, error

def queryItems(table, keys=[]):
    '''
    This function takes a list of geohashes and returns all the places
    in our database starting with it
    :table: (str) Name of the datatable to query
    :keys: ([str]) List of geohashes to look for
    Returns:
    :responses: A list of all places found in database
    '''
    d_table = dynamodb.Table(table)

    responses = []
    for geohash in keys:
        responses += d_table.query(
            KeyConditionExpression=Key('id').eq(geohash)
        )["Items"]
    
    return responses

def fetchAllPlacesFromDatabase(table):
    '''
    This function takes a list of geohashes and returns all the places
    in our database starting with it
    :table: (str) Name of the datatable to query
    :keys: ([str]) List of geohashes to look for
    Returns:
    :responses: A list of all places found in database
    '''
    d_table = dynamodb.Table(table)

    responses = d_table.scan(FilterExpression=Attr("current_popularity").ne("null"))["Items"]
    
    return responses

def fetchPlacesFromDatabase(geohashes):
    '''
    This function takes in a list of geohashes and returns the places
    informations that are held in our database
    :geohashes: ([str]) List of geohashes to query from database
    Returns:
    :places: ([object]) A list of places informations
    '''

    response = queryItems(PLACES_TABLE, keys=geohashes)
    return response

def getGeohashesThatNeedToBeUpdated():
    '''
    This function scans the dynamodb table and finds all geohashes
    that have been queried in the last 15 minutes.
    '''

    now = datetime.now().timestamp()
    fifteen_min_before = now - 900
    
    d_table = dynamodb.Table("geohashes-dev")

    # We get all five_digits geohashes that have been queried in the last 15 minutes
    hashes_to_update = d_table.scan(
        FilterExpression=Key('last_query').GreaterThanEquals(fifteen_min_before),
        AttributesToGet=["geohash"]
    )["Items"]

    return hashes_to_update