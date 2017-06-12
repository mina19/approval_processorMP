import json

#### load all the lvalert_type=='new' json files we will need

pipeline_names = ['cwb',
                  'gstlal', 
                  'mbta', 
                  'olib', 
                  'pycbc']

lvalerts = {} # dictionary of lvalert jsons where key is pipeline, value is the lvalert json

for pipeline in pipeline_names:
    with open('{0}.json'.format(pipeline), 'r') as f:
        lvalerts[pipeline] = json.load(f)
        f.close()

#### determine the type of test we want to conduct
#### this means modifying the jsons we have just loaded

test_types = ['burst_only',
              'cbc_only',
              'combination',
              ]

print('grouper test_types are: \n')
for test_type in test_types:
    print(test_type)

test_type = raw_input('Which grouper test do you want to run? ')

print('\nWe can also run tests where more than one grouper will be formed.')
print('This means the event gpstimes will be spaced just enough apart that two groupers will be formed.')
print('Do you want to form more than one grouper?')
more_than_one_group = raw_input('Y or N: ')

print('\nWe can also send in a late trigger.')
print('This means after grouper has made its selection for EM_Selected, we can send in a late trigger.')
print('Do you want to send a late trigger?')
late_trigger = raw_input('Y or N: ')

#### now we know what kind of test we want to conduct, so we deal with each case
if test_type=='burst_only':
    pipelines = ['cwb',
                 'olib']

if test_type=='cbc_only':
    pipelines = ['gstlal',
                 'mbta',
                 'pycbc']

if test_type=='combination':
    pipelines = ['cwb',
                 'gstlal',
                 'mbta',
                 'olib',
                 'pycbc']

#### come up with random far's for each json in pipelines
import random
fars = {} # dictionary of far's for checking our test

for i in range(len(pipelines)):
    random_far = random.uniform(10**-8, 10**-7)
    lvalerts[pipelines[i]]['object']['far'] = random_far
    fars[pipelines[i]] = random_far

#### alter the gpstimes first so that they are all within 1 second of each other
import time
current_time = time.time()

for i in range(len(pipelines)):
    lvalerts[pipelines[i]]['object']['gpstime'] = current_time + random.random()

import ConfigParser
config = ConfigParser.SafeConfigParser()
config.read('/home/guest/approval_processorMP/etc/childConfig-approval_processorMPtest.ini')

#### next alter the gpstimes again if more than one grouper is being created
if more_than_one_group=='Y':
    grouperWin = config.getfloat('grouper', 'grouperWin')
    sample = random.sample(pipelines, 1)[0] # randomly select which one gets sent with a gpstime that is spaced out by more than grouperWin from the others
    lvalerts[sample]['object']['gpstime'] += grouperWin
    lvalerts[sample]['object']['gpstime'] += 1 # add one more second just to be sure that more than 1 grouper will be created

#### next alter the graceid's so that there's no issue with trying to access event in gracedb
for i in range(len(pipelines)):
    lvalerts[pipelines[i]]['object']['graceid'] = 'G_{0}'.format(i)
    lvalerts[pipelines[i]]['uid'] = 'G_{0}'.format(i)

#### next create the json files we will send
for i in range(len(pipelines)):
    jsonfile = open('{0}test.json'.format(pipelines[i]), 'w')
    jsonfile.write(json.dumps(lvalerts[pipelines[i]]))
    jsonfile.close()

### next send these json files out, being careful of whether we want to send a late trigger or not
import os
import subprocess

def run(cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        (output, err) = p.communicate()
        output = output.replace('\n','')
        return output

decisionWin = config.getfloat('grouper', 'decisionWin') # get the decisionWin from the config file

homedir = os.path.expanduser('~')

#### now send triggers
if late_trigger=='N':
    for i in range(len(pipelines)):
        time.sleep(5)
        print('sending {0}test.json'.format(pipelines[i]))
        run('/usr/local/bin/lvalert_send -N {0}/.netrc --server lvalert.cgca.uwm.edu --node min-a.cho-test --file {1}test.json'.format(homedir, pipelines[i]))

if late_trigger=='Y':
    sample = random.sample(pipelines, 1)[0] # randomly select which one gets sent late
    for i in range(len(pipelines)):
        if pipelines[i]==sample:
            pass
        else:
            time.sleep(5)
            print('sending {0}test.json'.format(pipelines[i]))
            run('/usr/local/bin/lvalert_send -N {0}/.netrc --server lvalert.cgca.uwm.edu --node min-a.cho-test --file {1}test.json'.format(homedir, pipelines[i]))
    #### at this point we've sent everything but the late trigger
    time.sleep(decisionWin)
    time.sleep(5) # wait an extra 5 seconds just to make sure this event is sent well after a decision is reached for the first grouper object
    print('sending {0}test.json'.format(sample))
    run('/usr/local/bin/lvalert_send -N {0}/.netrc --server lvalert.cgca.uwm.edu --node min-a.cho-test --file {1}test.json'.format(homedir, sample))


#### print out information so that we know
print('\nPrinting out graceid -- pipeline -- far')
for pipeline in pipelines:
    print('{0} -- {1} -- {2}'.format(lvalerts[pipeline]['uid'], pipeline, fars[pipeline]))
