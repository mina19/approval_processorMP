#!/usr/bin/python
import os
import subprocess
import re
import time

def run(cmd):
	p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
	(output, err) = p.communicate()
	output = output.replace('\n','')
	return output

dir = os.path.expanduser('~')

def updateGPStime():
    '''update the GPStime in the triggers that are sent'''
    # Get current gpstime
    gpstime = run('/usr/bin/lalapps_tconvert now')
    gpstime = str(gpstime)+'.1200'

    #update trigger_submitted.txt to reflect this gpstime
    trigger = open('{0}/trigger_template.txt'.format(dir), 'r')
    text = trigger.read()
    start_time = re.findall(r'start:      (.*) (.*)', text)
    trigger.close()

    text = text.replace(start_time[0][0], gpstime)
    trigger = open('{0}/trigger_submitted.txt'.format(dir), 'w')
    trigger.write(text)
    trigger.close()

# Submit new event to GraceDb, this is for the throttling part, so let's add 3. 2 is the threshold for the default pipeline throttle
updateGPStime()
for i in range(3):
    graceid = run('/usr/bin/gracedb --service-url=https://gracedb.ligo.org/api Test CWB2G {0}/trigger_submitted.txt'.format(dir))
    run('/usr/bin/gracedb log --tag-name=\'analyst_comments\' {0} \'This is a fake event for testing PipelineThrottle. Event should not be labeled as EM_Throttled because event gpstimes are within 1 second of other triggers and thus are not counted as distinct triggers by approval processor.\''.format(graceid))
    time.sleep(5)

time.sleep(20)
# Next we're going to send the resetThrottle command
run('approvalprocessor_commandMP --node=min-a.cho-test group,Test pipeline,CWB2G resetThrottle')

time.sleep(20)
# Next we're going to submit 3 triggers and make sure they do become labeled as EM_Throttled
# this means they need distinct event gpstimes
for i in range(3):
    updateGPStime()
    graceid = run('/usr/bin/gracedb --service-url=https://gracedb.ligo.org/api Test CWB2G {0}/trigger_submitted.txt'.format(dir))
    run('/usr/bin/gracedb log --tag-name=\'analyst_comments\' {0} \'This is a fake event for testing PipelineThrottle. Event should be labeled as EM_Throttled because it is sent after the reset throttle method has been called but is part of a second set of triggers with distinct trigger times to mimic a misbehaving pipeline.\''.format(graceid))
    time.sleep(5)

time.sleep(20)
# Next we're going to send the resetThrottle command
run('approvalprocessor_commandMP --node=min-a.cho-test group,Test pipeline,CWB2G resetThrottle')

graceid = run('/usr/bin/gracedb --service-url=https://gracedb.ligo.org/api Test CWB2G {0}/trigger_submitted.txt'.format(dir))
run('/usr/bin/gracedb log --tag-name=\'analyst_comments\' {0} \'This is a fake event for testing PipelineThrottle. Event should NOT be labeled as EM_Throttled because it is sent after the reset method has been called and only one has been sent.\''.format(graceid))

