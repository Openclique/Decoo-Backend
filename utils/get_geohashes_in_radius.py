import numpy
import math
from geolib import geohash

def destinationPoint(lat, lng, brng, dist, index):
    '''
    This function returns the coordinates of a points of a direction
    on a radius around specific coordinates
    Returns:
    :direction: enum('n', 'ne', etc)
    :latitude: latitude coordinates
    :longitude: longitude coordinates
    :geohash: 10 digits geohash of the point
    '''

    rad = 6371                  # earths mean radius
    dist2 = dist/rad             # convert dist to angular distance in radians
    brng = numpy.deg2rad(brng)  # convert to radians
    lat1 = numpy.deg2rad(lat) 
    lon1 = numpy.deg2rad(lng)

    lat2 = math.asin(math.sin(lat1)*math.cos(dist2) + math.cos(lat1)*math.sin(dist2)*math.cos(brng) )
    lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(dist2)*math.cos(lat1),math.cos(dist2)-math.sin(lat1)*math.sin(lat2))
    lon2 = math.fmod(lon2 + 3*math.pi, 2*math.pi) - math.pi  # normalise to -180..+180º
    lat2 = numpy.rad2deg(lat2)
    lon2 = numpy.rad2deg(lon2)

    return lat2, lon2, geohash.encode(lat2, lon2, 10), dist

def getGeohashesInRadius(latitude, longitude, radius):
    '''
    This function takes in a latitude, a longitude, and a radius, and returns
    a list of geohashes at different precisions (5, 6, 7 digits)
    '''
    n = 16
    bearings = range(0, int(360-(360/n)), int(360/n)) # create array of all bearings needed from lat/lng

    points = [(latitude, longitude, geohash.encode(latitude, longitude, 10), 0)]

    # We get all the geohashes on the 8 cardinal points of a radius around us
    # We expand the radius to get as many different geohashes zones as possible
    for step in range(1, radius + 1):
        for index, brng in enumerate(bearings):
            points.append(destinationPoint(latitude, longitude, brng, step, index))
    
    track = {
        "five_digits": [],
        "six_digits": [],
        "seven_digits": []
    }

    # Then we keep track of how many different geohashes we have at different precision levels
    for _, _, h, _ in points:
        if h[:5] not in track["five_digits"]:
            track["five_digits"].append(h[:5])
        if h[:6] not in track["six_digits"]:
            track["six_digits"].append(h[:6])
        if h[:7] not in track["seven_digits"]:
            track["seven_digits"].append(h[:7])

    return track

if __name__ == '__main__':
    hashes = getGeohashesInRadius(34.0194, -118.411, 10)

    print(len(hashes["five_digits"]))
    print(hashes["five_digits"])

    print(len(hashes["six_digits"]))
    print(hashes["six_digits"])

    print(len(hashes["seven_digits"]))
    print(hashes["seven_digits"])