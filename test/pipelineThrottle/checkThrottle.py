from eventDictClassMethods import *

repoDirFile = open('repoDir.txt', 'r')
repoDir = repoDirFile.read()
repoDirFile.close()

repoDir = repoDir.strip('\n')
FAKEDB_DIR = repoDir + '/approval_processorMP/test/FAKE_DB'
g = initGraceDb(FAKEDB_DIR)

EM_Throttled = []
query_string = 'EM_Throttled'
EM_ThrottledEvents = g.events(query_string)

for event in EM_ThrottledEvents:
    graceid = event['graceid']
    EM_Throttled.append(graceid)

print('EM_Throttled events: {0}'.format(EM_Throttled))
print('Only events G000000, G000001, and G000002 should be EM_Throttled')
