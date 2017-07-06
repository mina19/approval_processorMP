from eventDictClassMethods import *
from astropy.time import Time
client = "https://gracedb-test.ligo.org/api/"
g = initGraceDb(client)

query_string = "1181000000 .. 1184000000" 
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
        if dt<0:
            print('weird event: {0}'.format(graceid))
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
num_bins = 100
n, bins, patches = plt.hist(injectionDelays, num_bins, facecolor='green')
plt.title('V1 Injection Comment Delays')
plt.xlabel('Seconds')
plt.ylabel('Frequency')
ax.xaxis.set_major_locator(majorLocator)
ax.xaxis.set_major_formatter(majorFormatter)
ax.xaxis.set_minor_locator(minorLocator)
plt.show()

# len(injectionDelays) = 104
# len(noInjectionComment) = 150
# np.mean(injectionDelays) = 236.54
# np.std(injectionDelays) = 312.21
# min(injectionDelays) = 56


majorLocator = MultipleLocator(500)
majorFormatter = FormatStrFormatter('%d')
minorLocator = MultipleLocator(100)

DQDelaysFig, ax = plt.subplots()
num_bins = 100
n, bins, patches = plt.hist(DQDelays, num_bins, facecolor='blue')
plt.title('V1 DQ Comment Delays')
plt.xlabel('Seconds')
plt.ylabel('Frequency')
ax.xaxis.set_major_locator(majorLocator)
ax.xaxis.set_major_formatter(majorFormatter)
ax.xaxis.set_minor_locator(minorLocator)
plt.show()

# len(DQDelays) = 187
# len(noDQComment) = 67
# np.mean(DQDelays) = 491.053
# np.std(DQDelays) = 783.633
# min(DQDelays) = 16

noDQComment = [u'G250132', u'G250131', u'G250136', u'G249923', u'G249920', u'G250178', u'G249926', u'G249924', u'G249925', u'G249928', u'G250429', u'G250428', u'G250425', u'G250424', u'G250427', u'G249949', u'G250177', u'G249957', u'G249956', u'G249955', u'G249954', u'G249952', u'G249951', u'G249958', u'G249921', u'G250227', u'G250100', u'G250173', u'G250172', u'G250170', u'G250175', u'G250010', u'G250182', u'G250183', u'G249963', u'G250169', u'G249919', u'G250379', u'G250378', u'G250377', u'G250376', u'G250397', u'G250396', u'G250395', u'G250393', u'G250392', u'G250391', u'G250390', u'G250399', u'G250398', u'G250402', u'G250401', u'G250400', u'G250366', u'G250384', u'G250385', u'G250386', u'G250387', u'G250380', u'G250382', u'G250383', u'G250222', u'G250388', u'G250389', u'G249930', u'G249929', u'G250158']

noInjectionComment = [u'G250132', u'G250131', u'G250136', u'G249922', u'G249923', u'G249920', u'G249926', u'G249924', u'G249925', u'G249928', u'G250429', u'G250428', u'G250026', u'G250425', u'G250424', u'G250427', u'G249949', u'G249980', u'G250049', u'G250043', u'G250046', u'G250045', u'G249889', u'G249957', u'G249956', u'G249955', u'G249954', u'G249953', u'G249952', u'G249951', u'G249950', u'G250005', u'G249959', u'G249958', u'G249921', u'G250012', u'G249927', u'G250059', u'G250020', u'G250050', u'G250051', u'G250052', u'G250053', u'G250054', u'G250056', u'G250013', u'G250025', u'G249947', u'G250014', u'G250028', u'G249992', u'G250100', u'G249991', u'G249906', u'G249975', u'G249974', u'G249986', u'G249990', u'G250027', u'G249997', u'G250010', u'G249944', u'G249985', u'G249988', u'G249968', u'G249967', u'G250018', u'G249963', u'G249960', u'G250064', u'G250067', u'G250066', u'G250061', u'G250060', u'G250063', u'G250062', u'G250068', u'G249999', u'G249998', u'G249973', u'G250009', u'G250055', u'G249972', u'G250021', u'G249977', u'G249919', u'G250379', u'G250378', u'G249913', u'G249912', u'G250377', u'G250376', u'G249979', u'G250070', u'G250077', u'G250075', u'G250078', u'G250397', u'G250396', u'G250395', u'G250017', u'G250393', u'G250392', u'G250391', u'G250390', u'G249989', u'G250019', u'G250399', u'G250398', u'G250023', u'G250004', u'G250003', u'G250006', u'G249995', u'G249996', u'G249908', u'G250402', u'G250401', u'G250400', u'G250001', u'G249994', u'G250366', u'G249905', u'G250022', u'G249941', u'G249978', u'G250384', u'G250385', u'G250386', u'G250387', u'G250380', u'G250024', u'G250382', u'G250383', u'G250029', u'G250388', u'G250389', u'G249937', u'G249936', u'G249930', u'G250044', u'G249939', u'G249987', u'G250015', u'G249929', u'G250008', u'G250098', u'G250097', u'G250158', u'G250016']

V1eventsList = [u'G250238', u'G250239', u'G250132', u'G250131', u'G250136', u'G250230', u'G250231', u'G250232', u'G250233', u'G250234', u'G250235', u'G250236', u'G250237', u'G249922', u'G249923', u'G249920', u'G250178', u'G249926', u'G250328', u'G249924', u'G249925', u'G249928', u'G250329', u'G250429', u'G250428', u'G250026', u'G250425', u'G250424', u'G250427', u'G250130', u'G249949', u'G249980', u'G250308', u'G250304', u'G250306', u'G250300', u'G250301', u'G250302', u'G250303', u'G250049', u'G250043', u'G250177', u'G250046', u'G250045', u'G250176', u'G249889', u'G249957', u'G249956', u'G249955', u'G249954', u'G249953', u'G249952', u'G249951', u'G249950', u'G250005', u'G249959', u'G249958', u'G249921', u'G250012', u'G250331', u'G250330', u'G250333', u'G250332', u'G250334', u'G249927', u'G250059', u'G250020', u'G250050', u'G250051', u'G250052', u'G250053', u'G250054', u'G250229', u'G250056', u'G250228', u'G250013', u'G250025', u'G250326', u'G250327', u'G250324', u'G249947', u'G250289', u'G250323', u'G250285', u'G250284', u'G250287', u'G250286', u'G250281', u'G250280', u'G250283', u'G250282', u'G250014', u'G250028', u'G249992', u'G250267', u'G250266', u'G250264', u'G250263', u'G250261', u'G250260', u'G250227', u'G250269', u'G250268', u'G250100', u'G249991', u'G249906', u'G250298', u'G250299', u'G249975', u'G249974', u'G249986', u'G250292', u'G250293', u'G250290', u'G250291', u'G250296', u'G250297', u'G250199', u'G250198', u'G249990', u'G250027', u'G250274', u'G250275', u'G250276', u'G250277', u'G250270', u'G250271', u'G250272', u'G250273', u'G250173', u'G250172', u'G250171', u'G250170', u'G250278', u'G250279', u'G250175', u'G250174', u'G249997', u'G250010', u'G249944', u'G249985', u'G249988', u'G250182', u'G250183', u'G249968', u'G250181', u'G249967', u'G250018', u'G250259', u'G249963', u'G249960', u'G250064', u'G250067', u'G250066', u'G250061', u'G250060', u'G250063', u'G250062', u'G250068', u'G250241', u'G250240', u'G250243', u'G250242', u'G250245', u'G250244', u'G250247', u'G250246', u'G250249', u'G250248', u'G249999', u'G249998', u'G249973', u'G250009', u'G250055', u'G249972', u'G250021', u'G250169', u'G249977', u'G249919', u'G250379', u'G250378', u'G249913', u'G249912', u'G250377', u'G250376', u'G249979', u'G250070', u'G250077', u'G250075', u'G250078', u'G250397', u'G250396', u'G250395', u'G250017', u'G250393', u'G250392', u'G250391', u'G250390', u'G250256', u'G249989', u'G250252', u'G250019', u'G250399', u'G250398', u'G250023', u'G250004', u'G250003', u'G250006', u'G249995', u'G249996', u'G249908', u'G250402', u'G250401', u'G250400', u'G250001', u'G249994', u'G250366', u'G249905', u'G250022', u'G249941', u'G249978', u'G250384', u'G250385', u'G250386', u'G250387', u'G250380', u'G250024', u'G250382', u'G250383', u'G250029', u'G250222', u'G250220', u'G250388', u'G250389', u'G249937', u'G249936', u'G249930', u'G250322', u'G250044', u'G249939', u'G249987', u'G250288', u'G250015', u'G249929', u'G250008', u'G250098', u'G250319', u'G250318', u'G250317', u'G250316', u'G250315', u'G250097', u'G250158', u'G250016']




