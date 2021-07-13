import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')

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

    request = {
        'geohashes-dev': {
            'Keys': []
        }
    }

    # We create the request body
    for geohash in geohashes:
        request['geohashes']['Keys'].append({
            "geohash": geohash
        })

    print("Here is the batch get item request:")
    print(request)

    try:
        response = dynamodb.batch_get_item(
            RequestItems=request,
        )
        print("Successful get")
        print(response)
    except Exception as e:
        print("An error has occured:")
        print(e)
    
    return response


def batchGetItems(table, keys=[], sortKeys=[]):
    '''
    This function takes in a table name and a list of keys or sort keys, and returns
    all the items that are matching the pattern
    :table: (str) name of the dynamodb table to query
    :keys: (str) unique identifiers to query in table
    :sortKeys: (str) identifiers to look for in table
    '''

    d_table = dynamodb.Table(table)
