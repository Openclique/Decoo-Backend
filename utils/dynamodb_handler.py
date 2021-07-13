import boto3
from botocore.exceptions import ClientError
from datetime import datetime

dynamodb = boto3.resource('dynamodb')

def isUpToDate(dynamodb_hash):
    '''
    This function takes in a geohash element from the dynamodb table
    and checks if it is up to date (updated in the last 15 min)
    '''
    current_timestamp = int(datetime.now().timestamp())
    hash_last_update = dynamodb_hash["last_update"]

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
        "error": False,
        "to_update": [],
        "up_to_date": []
    }

    # We create the request body
    request = {
        'geohashes-dev': {
            'Keys': []
        }
    }
    for geohash in geohashes:
        request['geohashes-dev']['Keys'].append({
            "geohash": geohash
        })

    # Then we batch get the dynamodb table
    try:
        response = dynamodb.batch_get_item(
            RequestItems=request,
        )
        print("Successful get")
        print(response)
    except Exception as e:
        print("An error has occured:")
        print(e)
        ret["error"] = True
        return ret
    
    # We extract the informations we found in database 
    found_hashes = response["Responses"]["geohashes-dev"]

    # We then create the return
    ret["up_to_date"] = [h["geohash"] for h in found_hashes if isUpToDate(h)]
    ret["to_update"] = [h for h in geohashes if h not in ret["up_to_date"]]

    return ret


def batchGetItems(table, keys=[], sortKeys=[]):
    '''
    This function takes in a table name and a list of keys or sort keys, and returns
    all the items that are matching the pattern
    :table: (str) name of the dynamodb table to query
    :keys: (str) unique identifiers to query in table
    :sortKeys: (str) identifiers to look for in table
    '''

    d_table = dynamodb.Table(table)
