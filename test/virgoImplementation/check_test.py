from eventDictClassMethods import *

repoDirFile = open('repoDir.txt','r')
repoDir = repoDirFile.read()
repoDirFile.close()

repoDir = repoDir.strip('\n')
FAKEDB_DIR = repoDir + '/approval_processorMP/test/FAKE_DB'
g = initGraceDb(FAKEDB_DIR)

EM_READY = []
query_string = 'EM_READY'
EM_READYevents = g.events(query_string)

for event in EM_READYevents:
    graceid = event['graceid']
    EM_READY.append(graceid)

print(EM_READY)

DQV = []
query_string = 'DQV'
DQVevents = g.events(query_string)

for event in DQVevents:
    graceid = event['graceid']
    DQV.append(graceid)

print(DQV)
