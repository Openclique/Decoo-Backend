import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from datetime import datetime
from geolib import geohash
from decimal import Decimal
import json

from utils import functions

dynamodb = boto3.resource('dynamodb', region_name='us-west-1')
PLACES_TABLE = "places-prod"
GEOHASHES_TABLE = "geohashes-prod"
TWENTY_FOUR_HOURS = 86400


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

def shouldFetchNewPlaces():
    """This function returns true if we haven't tried to fetch
    new places in the last 24 hours.
    It also update the db to remember that we will now update it
    """

    info = None
    ret = dynamodb.Table(GEOHASHES_TABLE).get_item(
        Key={
            "geohash": "ALL"
        }
    )

    if "Item" in ret.keys():
        info = ret["Item"]
    
    should_fech_new_places = (int(datetime.now().timestamp()) - info["last_update"] > TWENTY_FOUR_HOURS)

    return should_fech_new_places

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
        "up_to_date": [],
        "error": True
    }

    response, error = batchGetItems(GEOHASHES_TABLE, keys=geohashes)
    
    if error:
        return ret

    # We extract the informations we found in database 
    found_hashes = response["Responses"][GEOHASHES_TABLE]

    # We then create the return object
    ret["up_to_date"] = [h["geohash"] for h in found_hashes if isUpToDate(h)]
    ret["to_update"] = [h for h in geohashes if h not in ret["up_to_date"]]
    ret["error"] = error

    return ret

def batchUpdatePlaces(places=[], get_new_points=False):
    '''
    This function takes in a list of places informations and add them into
    our database
    :places: ([object]) list of places informations queried from external APIs
    Returns:
    :bool: True if success, False if error
    '''

    print("Running batch update")
    with dynamodb.Table(PLACES_TABLE).batch_writer() as batch:

        # We loop through each place
        for place in places:

            # If the place doesn't have coordinates or forecast we simply skip it
            if not place['coordinates'] or not place['popular_times'] or not place["current_popularity"]:
                continue

            # We convert lat, lon to 5 and 10 digits geohashes
            ten_digits_hash = geohash.encode(place['coordinates']["lat"], place['coordinates']["lng"], 10)
            five_digits_hash = ten_digits_hash[:5]
            place["id"] = five_digits_hash
            place["geohash"] = ten_digits_hash

            # Then we update the geohashes table
            ddb_data = json.loads(json.dumps(place), parse_float=Decimal)

            # Then we update the places table
            batch.put_item(Item=ddb_data)

    # We update the db to remember that we queried new points
    if get_new_points:
        ret = dynamodb.Table(GEOHASHES_TABLE).put_item(
            Item=json.loads(json.dumps({"geohash": "ALL", "last_update": datetime.now().timestamp()}), parse_float=Decimal)
        )

    return True

def rememberCurrentQuery(hashes=[]):
    '''
    This function takes in a list of hashes that got queried and updates the database

    Args:
        :hashes: ([str]) list of 5 digits hashes
    Returns:
        :bool: True if success, False if error
    '''

    with dynamodb.Table(GEOHASHES_TABLE).batch_writer() as batch:

        # We loop through each place
        for hash in hashes:
            
            current_hash_item = None
            ret = dynamodb.Table(GEOHASHES_TABLE).get_item(
                Key={
                    "geohash": hash
                }
            )

            if "Item" in ret.keys():
                current_hash_item = ret["Item"]
                
            obj = {
                "geohash": hash,
                "last_update": 0 if current_hash_item is None else current_hash_item["last_update"],
                "last_query": datetime.now().timestamp(),
                "queried_count": 1 if current_hash_item is None else current_hash_item["queried_count"] + 1
            }

            ddb_data = json.loads(json.dumps(obj, default=functions.decimal_serializer), parse_float=Decimal)
            print(ddb_data)
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
        print(f"Error when batch getting items:")
        print(e)
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
    that have been queried in the last 15 minutes or more than 2 hours ago.

    This way we make sure that in zones where there is a lot of people we are
    always updated, and in less crowded zones we keep informations relevant enough.
    '''

    now = datetime.now().timestamp()
    fifteen_min_before = now - 900
    two_hours_ago = now - (900 * 8)
    
    d_table = dynamodb.Table(GEOHASHES_TABLE)

    # We get all five_digits geohashes that have been queried in the last 15 minutes,
    # or more than 2 hours ago.
    hashes_to_update = d_table.scan(
        FilterExpression=Attr('last_query').gte(Decimal(fifteen_min_before)) | (Attr('last_query').lte(Decimal(two_hours_ago)) & Attr('last_update').lte(Decimal(two_hours_ago))),
    )["Items"]

    return [h["geohash"] for h in hashes_to_update]

def rememberHashesUpdate(hashes):
    """This function updates the geohashes table to remember that we've
    updated them

    Args:
        hashes (list): List of geohashes that got updated
    """
    print("in")
    print(hashes)
    with dynamodb.Table(GEOHASHES_TABLE).batch_writer() as batch:

        # We loop through each place
        for hash in hashes:
            
            current_hash_item = None
            ret = dynamodb.Table(GEOHASHES_TABLE).get_item(
                Key={
                    "geohash": hash
                }
            )

            if "Item" in ret.keys():
                current_hash_item = ret["Item"]

            obj = {
                "geohash": hash,
                "last_update": datetime.now().timestamp(),
                "last_query": current_hash_item["last_query"],
                "queried_count": current_hash_item["queried_count"]
            }

            ddb_data = json.loads(json.dumps(obj, default=functions.decimal_serializer), parse_float=Decimal)
            print(ddb_data)
            # Then we update the places table
            batch.put_item(Item=ddb_data)