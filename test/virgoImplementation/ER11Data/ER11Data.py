from eventDictClassMethods import *
from astropy.time import Time
client = "https://gracedb-test.ligo.org/api/"
g = initGraceDb(client)

# Get ER11 Data from 6/16 08:00:00 UTC to 6/26 08:00:00 UTC
query_string = "1181635218 .. 1182499218" 
allEvents = g.events(query_string)

V1events = {}
injectionCommentTimes = {}
DQCommentTimes = {}

def convertISOstr(string):
    '''
    converts strings of the form 2017-07-06 05:45:55 UTC into 
    gpstime
    '''
    t = Time(string.strip(' UTC'), format='iso', scale='utc')
    t = Time(t, format='gps')
    return t.value

def convertISOTstr(string):
    '''
    converts string of the form 2017-07-06T05:45:55+00:00 into
    gpstime
    '''
    string = string.replace('T', ' ')
    string = string.replace('+00:00', '')
    t = Time(string, format='iso', scale='utc')
    t = Time(t, format='gps')
    return t.value

for event in allEvents:
    instruments = event['instruments']
    if 'V1' in instruments:
        graceid = event['graceid']
        created = event['created'] #this is in ISO format
        V1events[graceid]=convertISOstr(created)
        log_dicts = g.logs(graceid).json()['log']
        for message in log_dicts:
            comment = message['comment']
            if 'V1 hardware injection' in comment and comment.endswith('injections'):
                commentcreation = message['created'] # this is in ISOT format
                injectionCommentTimes[graceid] = convertISOTstr(commentcreation)
            elif 'V1 veto channel' in comment and comment.endswith('vetoed'):
                commentcreation = message['created'] # this is in ISOT format
                DQCommentTimes[graceid] = convertISOTstr(commentcreation)
            else:
                pass
    else:
        pass





injectionDelays = []
noInjectionComment = []
for graceid in V1events:
    if graceid in injectionCommentTimes:
        dt = injectionCommentTimes[graceid] - V1events[graceid]
        injectionDelays.append(dt)
    else:
        noInjectionComment.append(graceid)


DQDelays = []
noDQComment = []
for graceid in V1events:
    if graceid in DQCommentTimes:
        dt = DQCommentTimes[graceid] - V1events[graceid]
        DQDelays.append(dt)
    else:
        noDQComment.append(graceid)


import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

majorLocator = MultipleLocator(100)
majorFormatter = FormatStrFormatter('%d')
minorLocator = MultipleLocator(10)

injectionDelaysFig, ax = plt.subplots()
num_bins = 1000
n, bins, patches = plt.hist(injectionDelays, num_bins, facecolor='green')
plt.title('V1 Injection Comment Delays')
plt.xlabel('Seconds')
plt.ylabel('Frequency')
ax.xaxis.set_major_locator(majorLocator)
ax.xaxis.set_major_formatter(majorFormatter)
ax.xaxis.set_minor_locator(minorLocator)
plt.show()

# len(injectionDelays) = 104
# len(noInjectionComment) = 119
# min(injectionDelays) = 56.0
# max(injectionDelays) = 1739.0
# np.mean(injectionDelays) = 236.54
# np.std(injectionDelays) = 312.21



majorLocator = MultipleLocator(500)
majorFormatter = FormatStrFormatter('%d')
minorLocator = MultipleLocator(100)

DQDelaysFig, ax = plt.subplots()
num_bins = 1000
n, bins, patches = plt.hist(DQDelays, num_bins, facecolor='blue')
plt.title('V1 DQ Comment Delays')
plt.xlabel('Seconds')
plt.ylabel('Frequency')
ax.xaxis.set_major_locator(majorLocator)
ax.xaxis.set_major_formatter(majorFormatter)
ax.xaxis.set_minor_locator(minorLocator)
plt.show()

# len(DQDelays) = 187
# len(noDQComment) = 36
# min(DQDelays) = 16.0
# max(DQDelays) = 5736.0
# np.mean(DQDelays) = 491.053
# np.std(DQDelays) = 783.633

import re
def convertGPStime(float):
    '''
    converts float gpstime into UTC time string of the form
    07-06
    '''
    t = Time(float, format='gps')
    t = Time(t, format='iso')
    t = re.findall('2017-0(.*)-(.*) ', t.value)
    return str(t[0][0]) + '/' + str(t[0][1])


noInjectionCommentTimes = []
for graceid in noInjectionComment:
    event_dict = g.events(graceid).next()
    createdTime = event_dict['created']
    noInjectionCommentTimes.append(convertISOstr(createdTime))

noInjectionCommentTimesFig, ax = plt.subplots()
num_bins = 1000
n, bins, patches = plt.hist(noInjectionCommentTimes, num_bins, facecolor='red')
plt.title('Missing V1 Injection Comment')
plt.xlabel('GPSTime')
plt.ylabel('Frequency')
ax.set_xlim([1181635218, 1182499218])
ax.xaxis.set_ticks(np.arange(1181635218, 1182499218, 86400))
ax.xaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
plt.show()



noDQCommentTimes = []
for graceid in noDQComment:
    event_dict = g.events(graceid).next()
    createdTime = event_dict['created']
    noDQCommentTimes.append(convertISOstr(createdTime))

noDQCommentTimesFig, ax = plt.subplots()
num_bins = 1000
n, bins, patches = plt.hist(noDQCommentTimes, num_bins, facecolor='red')
plt.title('Missing V1 DQ Comment')
plt.xlabel('GPSTime')
plt.ylabel('Frequency')
ax.set_xlim([1181635218, 1182499218])
ax.xaxis.set_ticks(np.arange(1181635218, 1182499218, 86400))
ax.xaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
plt.show()

