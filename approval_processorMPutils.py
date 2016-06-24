description = "utilities for approval_processorMP.py"
author = "Min-A Cho mina19@umd.edu"

#-----------------------------------------------------------------------
# Import packages
#-----------------------------------------------------------------------
#from ligo.lvalert import lvalertMPutils as utils
from ligo.gracedb.rest import GraceDb, HTTPError
import subprocess as sp
import re
import operator
import functools
import os
import json
import random
import time
import datetime
import pickle

#-----------------------------------------------------------------------
# Fetch childConfig-approval_processorMP.ini parameters
#-----------------------------------------------------------------------
import ConfigParser
config = ConfigParser.SafeConfigParser()
config.read('{0}/childConfig-approval_processorMP.ini'.format(os.getcwd()))

client = config.get('general', 'client')
voeventerror_email = config.get('general', 'voeventerror_email')
force_all_internal = config.get('general', 'force_all_internal')
preliminary_internal = config.get('general', 'preliminary_internal')

hardware_inj = config.get('labelCheck', 'hardware_inj')

default_farthresh = config.getfloat('farCheck', 'default_farthresh')

time_duration = config.getfloat('injectionCheck', 'time_duration')

humanscimons = config.get('operator_signoffCheck', 'humanscimons')

advocates = config.get('advocate_signoffCheck', 'advocates')
advocate_text = config.get('advocate_signoffCheck', 'advocate_text')
advocate_email = config.get('advocate_signoffCheck', 'advocate_email')

ignore_idq = config.get('idq_joint_fapCheck', 'ignore_idq')
default_idqthresh = config.getfloat('idq_joint_fapCheck', 'default_idqthresh')
idq_pipelines = config.get('idq_joint_fapCheck', 'idq_pipelines')
idq_pipelines = idq_pipelines.replace(' ','')
idq_pipelines = idq_pipelines.split(',')

skymap_ignore_list = config.get('have_lvem_skymapCheck', 'skymap_ignore_list')

#-----------------------------------------------------------------------
# Set up logging
#-----------------------------------------------------------------------
import logging
logger = logging.getLogger('approval_processorMP')
logfile = config.get('general', 'approval_processorMP_logfile')
homedir = os.path.expanduser('~')
logging_filehandler = logging.FileHandler('{0}/public_html{1}'.format(homedir, logfile))
logging_filehandler.setLevel(logging.INFO)
logger.setLevel(logging.INFO)
logger.addHandler(logging_filehandler)

#-----------------------------------------------------------------------
# Instantiate GraceDB client
#-----------------------------------------------------------------------
g = GraceDb('{0}'.format(client))

#-----------------------------------------------------------------------
# Tasks when currentstate of event is new_to_preliminary
#-----------------------------------------------------------------------
new_to_preliminary = [
    'farCheck',
    'labelCheck',
    'injectionCheck'
    ]

#-----------------------------------------------------------------------
# Tasks when currentstate of event is preliminary_to_initial
#-----------------------------------------------------------------------
preliminary_to_initial = [
    'farCheck',
    'labelCheck',
    'have_lvem_skymapCheck',
    'idq_joint_fapCheck'
    ]
if humanscimons=='yes':
    preliminary_to_initial.append('operator_signoffCheck')
if advocates=='yes':
    preliminary_to_initial.append('advocate_signoffCheck')

#-----------------------------------------------------------------------
# Tasks when currentstate of event is initial_to_update
#-----------------------------------------------------------------------
initial_to_update = [
    'farCheck',
    'labelCheck',
    'have_lvem_skymapCheck'
    ]

#-----------------------------------------------------------------------
# Creating event dictionaries
#-----------------------------------------------------------------------
class EventDict:
    EventDicts = {}
    def __init__(self, dictionary, graceid):
        self.dictionary = dictionary
        self.graceid = graceid
    def CreateDict(self):
        class_dict = {}
        class_dict['advocate_signoffCheckresult'] = None
        class_dict['advocatelogkey'] = 'no'
        class_dict['advocatesignoffs'] = []
        class_dict['currentstate'] = 'new_to_preliminary'
        class_dict['far'] = self.dictionary['far']
        class_dict['farCheckresult'] = None
        class_dict['farlogkey'] = 'no'
        class_dict['gpstime'] = self.dictionary['gpstime']
        class_dict['graceid'] = self.graceid
        class_dict['group'] = self.dictionary['group']
        class_dict['have_lvem_skymapCheckresult'] = None
        class_dict['idq_joint_fapCheckresult'] = None
        class_dict['idqlogkey'] = 'no'
        class_dict['idqvalues'] = {}
        class_dict['injectionCheckresult'] = None
        class_dict['injectionsfound'] = None
        class_dict['injectionlogkey'] = 'no'
        class_dict['instruments'] = str(self.dictionary['instruments']).split(',')
        class_dict['jointfapvalues'] = {}
        class_dict['labelCheckresult'] = None
        class_dict['labels'] = self.dictionary['labels'].keys()
        class_dict['lastsentskymap'] = None
        class_dict['lvemskymaps'] = {}
        class_dict['operator_signoffCheckresult'] = None
        class_dict['operatorlogkey'] = 'no'
        class_dict['operatorsignoffs'] = {}
        class_dict['pipeline'] = self.dictionary['pipeline']
        if 'search' in self.dictionary.keys():
            class_dict['search'] = self.dictionary['search']
        else:
            class_dict['search'] = ''
        class_dict['voeventerrors'] = []
        class_dict['voevents'] = []
        EventDict.EventDicts['{0}'.format(self.graceid)] = class_dict
        logger.info('{0} -- {1} -- Created event dictionary for {1}.'.format(convertTime(), self.graceid))

#-----------------------------------------------------------------------
# Saving event dictionaries
#-----------------------------------------------------------------------
def saveEventDicts():
    EventDicts = EventDict.EventDicts
    pickle.dump(EventDicts, open('{0}/public_html/EventDicts.p'.format(homedir), 'wb'))
    f = open('{0}/public_html/EventDicts.txt'.format(homedir), 'w')
    Dicts = sorted(EventDicts.keys())
    for dict in Dicts:
        f.write('{0}\n'.format(dict))
        keys = sorted(EventDicts[dict].keys())
        for key in keys:
            f.write('    {0}: {1}\n'.format(key, EventDicts[dict][key]))
        f.write('\n')
    f.close()

#-----------------------------------------------------------------------
# Loading event dictionaries
#-----------------------------------------------------------------------
def loadEventDicts():
    try:
        EventDict.EventDicts = pickle.load(open('{0}/public_html/EventDicts.p'.format(homedir), 'rb'))
    except:
        pass

#-----------------------------------------------------------------------
# parseAlert
#-----------------------------------------------------------------------
def parseAlert(alert):
    # get the event dictionary for approval_processorMP's use
    graceid = alert['uid']
    if graceid in EventDict.EventDicts.keys():
        event_dict = EventDict.EventDicts['{0}'.format(graceid)]
    else:
        # query gracedb to get information
        event_dict = g.events(graceid).next()
        EventDict(event_dict, graceid).CreateDict()
        event_dict = EventDict.EventDicts['{0}'.format(graceid)]
    saveEventDicts()

    # get alert specifics and event_dict information
    alert_type = alert['alert_type']
    description = alert['description']
    filename = alert['file']
    currentstate = event_dict['currentstate']

    # actions for each alert_type
    if alert_type=='label':
        if description=='PE_READY':
            logger.info('{0} -- {1} -- Sending update VOEvent.'.format(convertTime(), graceid))
            process_alert(event_dict, 'update')
            logger.info('{0} -- {1} -- State: {2} --> complete.'.format(convertTime(), graceid, currentstate))
            event_dict['currentstate'] = 'complete'

        elif description=='EM_READY':
            logger.info('{0} -- {1} -- Sending initial VOEvent.'.format(convertTime(), graceid))
            process_alert(event_dict, 'initial')
            logger.info('{0} -- {1} -- State: {2} --> initial_to_update.'.format(convertTime(), graceid, currentstate))
            event_dict['currentstate'] = 'initial_to_update'

        elif (checkLabels(hardware_inj, description.split()) > 0):
            voevents = sorted(event_dict['voevents'])
            if len(voevents) > 0:
                if 'retraction' in voevents[-1]:
                    return
                # there are existing VOEvents we've sent, but no retraction alert
                process_alert(event_dict, 'retraction')

    # 

    # run checks specific to currentstate of the event candidate
    passedcheckcount = 0

    if currentstate=='new_to_preliminary':
        for Check in new_to_preliminary:
            eval('{0}(event_dict)'.format(Check))
            checkresult = event_dict[Check + 'result']
            if checkresult==None:
               # need to add Check to queueByGraceID
                logger.info('{0} -- {1} -- Added {2} to queueByGraceID.'.format(convertTime(), graceid, Check))
                print 'Added {0} to queueByGraceID'.format(Check)
            elif checkresult==False:
                logger.info('{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate))
                logger.info('{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate))
                print 'Failed in the {0} state.'.format(currentstate)
                print 'currentstate now rejected.'
                event_dict['currentstate'] = 'rejected'
                return
            elif checkresult==True:
                print 'Do not need to add {0} to queue'.format(Check)
                passedcheckcount += 1
        if passedcheckcount==len(new_to_preliminary):
            logger.info('{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate))
            logger.info('{0} -- {1} -- Sending preliminary VOEvent.'.format(convertTime(), graceid))
            process_alert(event_dict, 'preliminary')
            logger.info('{0} -- {1} -- State: {2} --> preliminary_to_initial.'.format(convertTime(), graceid, currentstate))
            event_dict['currentstate'] = 'preliminary_to_initial'
            # notify the operators
            instruments = event_dict['instruments']
            for instrument in instruments:
                logger.info('{0} -- {1} -- Labeling {2}OPS.'.format(convertTime(), graceid, instrument))
                g.writeLabel(graceid, '{0}OPS'.format(instrument))
            # notify the advocates
            g.writeLabel(graceid, 'ADVREQ')
            os.system('echo \'{0}\' | mail -s \'{1} passed criteria for follow-up\' {2}'.format(advocate_text, graceid, advocate_email))
            # expose event to LV-EM
            url_perm_base = g.service_url + urllib.quote('events/{0}/perms/gw-astronomy:LV-EM:Observers/'.format(graceid))
            for perm in ['view', 'change']:
                url = url_perm_base + perm
                #g.put(url)

    elif currentstate=='preliminary_to_initial':
        for Check in preliminary_to_initial:
            eval('{0}(event_dict)'.format(Check))
            checkresult = event_dict[Check + 'result']
            if checkresult==None:
               # need to add Check to queueByGraceID
                logger.info('{0} -- {1} -- Added {2} to queueByGraceID.'.format(convertTime(), graceid, Check))
                print 'Added {0} to queueByGraceID'.format(Check)
            elif checkresult==False:
               # need to send retraction VOEvent or set DQV label
                logger.info('{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate))
                logger.info('{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate))
                print 'Failed in the {0} state.'.format(currentstate)
                print 'currentstate now rejected.'
                event_dict['currentstate'] = 'rejected'
                return
            elif checkresult==True:
                print 'Do not need to add {0} to queue'.format(Check)
                passedcheckcount += 1
        if passedcheckcount==len(preliminary_to_initial):
            logger.info('{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate))
            logger.info('{0} -- {1} -- Labeling EM_READY.'.format(convertTime(), graceid))
            g.writeLabel(graceid, 'EM_READY')

    elif currentstate=='initial_to_update':
        return

#-----------------------------------------------------------------------
# Utilities
#-----------------------------------------------------------------------
def convertTime():
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return st

#-----------------------------------------------------------------------
# farCheck
#-----------------------------------------------------------------------
def get_farthresh(pipeline, search):
    try:
        return config.getfloat('farCheck', 'farthresh[{0}.{1}]'.format(pipeline, search))
    except:
        return default_farthresh

def farCheck(event_dict):
    farCheckresult = event_dict['farCheckresult']
    if farCheckresult!=None:
        return farCheckresult
    else:
        far = event_dict['far']
        graceid = event_dict['graceid']
        pipeline = event_dict['pipeline']
        search = event_dict['search']
        farthresh = get_farthresh(pipeline, search)
        if far >= farthresh:
           # g.writeLog(graceid, 'AP: Candidate event rejected due to large FAR. {0} >= {1}'.format(far, farthresh), tagname='em_follow')
            event_dict['farlogkey'] = 'yes'
            logger.info('{0} -- {1} -- Rejected due to large FAR. {2} >= {3}'.format(convertTime(), graceid, far, farthresh))
            event_dict['farCheckresult'] = False
            return False
        elif far < farthresh:
           # g.writeLog(graceid, 'AP: Candidate event has low enough FAR.{0} < {1}'.format(far, farthresh), tagname='em_follow')
            event_dict['farlogkey'] = 'yes'
            logger.info('{0} -- {1} -- Low enough FAR. {2} < {3}'.format(convertTime(), graceid, far, farthresh))
            event_dict['farCheckresult'] = True
            return True

#-----------------------------------------------------------------------
# labelCheck
#-----------------------------------------------------------------------
def checkLabels(labels):
    if hardware_inj == 'yes':
        badlabels = ['DQV']
    else:
        badlabels = ['DQV', 'INJ']
    intersectionlist = list(set(badlabels).intersection(labels))
    return len(intersectionlist)

def labelCheck(event_dict):
    graceid = event_dict['graceid']
    labels = event_dict['labels']
    if checkLabels(labels) > 0:
        logger.info('{0} -- {1} -- Ignoring event due to INJ or DQV label.'.format(convertTime(), graceid))
        event_dict['labelCheckresult'] = False
        return False
    else:
        event_dict['labelCheckresult'] = True
        return True

#-----------------------------------------------------------------------
# injectionCheck
#-----------------------------------------------------------------------
def injectionCheck(event_dict):
    injectionCheckresult = event_dict['injectionCheckresult']
    if injectionCheckresult!=None:
        return injectionCheckresult
    else:
        eventtime = event_dict['gpstime']
        graceid = event_dict['graceid']
        from raven.search import query
        th = time_duration
        tl = -th
        Injections = query('HardwareInjection', eventtime, tl, th)
        event_dict['injectionsfound'] = len(Injections)
        if len(Injections) > 0:
            if hardware_inj=='no':
               # g.writeLog(graceid, 'AP: Ignoring new event because we found a hardware injection +/- {0} seconds of event gpstime.'.format(th), tagname = "em_follow")
                event_dict['injectionlogkey'] = 'yes'
                logger.info('{0} -- {1} -- Ignoring new event because we found a hardware injection +/- {2} seconds of event gpstime.'.format(convertTime(), graceid, th))
                event_dict['injectionCheckresult'] = False
                return False
            else:
               # g.writeLog(graceid, 'AP: Found hardware injection +/- {0} seconds of event gpstime but treating as real event in config.'.format(th), tagname = "em_follow")
                event_dict['injectionlogkey'] = 'yes'
                logger.info('{0} -- {1} -- Found hardware injection +/- {2} seconds of event gpstime but treating as real event in config.'.format(convertTime(), graceid, th))
                event_dict['injectionCheckresult'] = True
                return True
        elif len(Injections)==0:
           # g.writeLog(graceid, 'AP: No hardware injection found near event gpstime +/- {0} seconds.'.format(th), tagname="em_follow")
            event_dict['injectionlogkey'] = 'yes'
            logger.info('{0} -- {1} -- No hardware injection found near event gpstime +/- {2} seconds.'.format(convertTime(), graceid, th))
            event_dict['injectionCheckresult'] = True
            return True

#-----------------------------------------------------------------------
# have_lvem_skymapCheck
#-----------------------------------------------------------------------
def have_lvem_skymapCheck(event_dict):
    graceid = event_dict['graceid']
    currentstate = event_dict['currentstate']
    lvemskymaps = sorted(event_dict['lvemskymaps'].keys())

    if currentstate=='preliminary_to_initial':
        if len(lvemskymaps)>=1:
            event_dict['have_lvem_skymapCheckresult'] = True
            skymap = sorted(lvemskymaps)[-1]
            skymap = re.findall(r'-(\S+)', skymap)[0]
            logger.info('{0} -- {1} -- Initial skymap tagged lvem {2} available.'.format(convertTime(), graceid, skymap))
            return True
        else:
            event_dict['have_lvem_skymapCheckresult'] = None
            logger.info('{0} -- {1} -- No initial skymap tagged lvem available.'.format(convertTime(), graceid))
            return None

    elif (currentstate=='initial_to_update' or currentstate=='complete'):
        if len(lvemskymaps)>=2:
            if lvemskymap[-1]!=event_dict['lastsentskymap']:
                event_dict['have_lvem_skymapCheckresult'] = True
                skymap = sorted(lvemskymaps)[-1]
                skymap = re.findall(r'-(\S+)', skymap)[0]
                logger.info('{0} -- {1} -- Update skymap tagged lvem {2} available.'.format(convertTime(), graceid, skymap))
                return True
            else:
                event_dict['have_lvem_skymapCheckresult'] = None
                logger.info('{0} -- {1} -- No update skymap tagged lvem available.'.format(convertTime(), graceid))
                return None
        else:
            event_dict['have_lvem_skymapCheckresult'] = None
            logger.info('{0} -- {1} -- No update skymap tagged lvem available.'.format(convertTime(), graceid))
            return None

def current_lvem_skymap(event_dict):
    lvemskymaps = sorted(event_dict['lvemskymaps'].keys())
    if len(lvemskymaps)==0:
        return None
    else:
        skymap = sorted(lvemskymaps)[-1]
        skymap = re.findall(r'-(\S+)', skymap)[0]
        return skymap

def record_skymap(event_dict, skymap, submitter):
    lvemskymaps = sorted(event_dict['lvemskymaps'].keys())
    currentnumber = len(lvemskymaps) + 1
    skymapkey = '{0}'.format(currentnumber) + '-'+ skymap
    event_dict['lvemskymaps'][skymapkey] = submitter

#-----------------------------------------------------------------------
# idq_joint_fapCheck
#-----------------------------------------------------------------------
def get_idqthresh(pipeline, search):
    try:
        return config.getfloat('idq_joint_fapCheck', 'idqthresh[{0}.{1}]'.format(pipeline, search))
    except:
        return default_idqthresh

def record_idqvalues(event_dict, comment):
    graceid = event_dict['graceid']
    idqinfo = re.findall('minimum glitch-FAP for (.*) at (.*) with', comment)
    idqpipeline = idqinfo[0][0]
    idqdetector = idqinfo[0][1]
    minfap = re.findall('is (.*)', comment)
    minfap = float(minfap[0])
    detectorstring = '{0}.{1}'.format(idqpipeline, idqdetector)
    event_dict['idqvalues'][detectorstring] = minfap    
    logger.info('{0} -- {1} -- Got the minfap for {2} using {3} is {4}.'.format(convertTime(), graceid, idqdetector, idqpipeline, minfap))

def compute_joint_fap_values(event_dict):
    idqvalues = event_dict['idqvalues']
    jointfapvalues = event_dict['jointfapvalues']
    for idqpipeline in idq_pipelines:
        pipeline_values = []
        for key in idqvalues.keys():
            if idqpipeline in key:
                pipeline_values.append(idqvalues[key])
        jointfapvalues[idqpipeline] = functools.reduce(operator.mul, pipeline_values, 1)

def idq_joint_fapCheck(event_dict):
    group = event_dict['group']
    idq_joint_fapCheckresult = event_dict['idq_joint_fapCheckresult']
    if idq_joint_fapCheckresult!=None:
        return idq_joint_fapCheckresult
    elif group in ignore_idq:
        logger.info('{0} -- {1} -- Not using idq checks for events with group(s) {2}.'.format(convertTime(), graceid, ignore_idq))
        event_dict['idq_joint_fapCheckresult'] = True
        return True
    else:
        pipeline = event_dict['pipeline']
        search = event_dict['search']
        idqthresh = get_idqthresh(pipeline, search)
        compute_joint_fap_values(event_dict)
        graceid = event_dict['graceid']
        idqvalues = event_dict['idqvalues']
        idqlogkey = event_dict['idqlogkey']
        instruments = event_dict['instruments']
        jointfapvalues = event_dict['jointfapvalues']
        if len(idqvalues)==0:
            logger.info('{0} -- {1} -- Have not gotten all the minfap values yet.'.format(convertTime(), graceid))
        elif (0 < len(idqvalues) < (len(idq_pipelines)*len(instruments))):
            logger.info('{0} -- {1} -- Have not gotten all the minfap values yet.'.format(convertTime(), graceid))
            if (min(idqvalues.values() and jointfapvalues.values()) < idqthresh):
                if idqlogkey=='no':
                   # g.writeLog(graceid, 'AP: Finished running iDQ checks. Candidate event rejected because incomplete joint min-FAP value already less than iDQ threshold. {0} < {1}'.format(min(idqvalues.values() and jointfapvalues.values()), idqthresh), tagname='em_follow')
                    event_dict['idqlogkey']='yes'
                logger.info('{0} -- {1} -- Failed iDQ check: {2} < {3}. Labeling with DQV.'.format(convertTime(), graceid, min(idqvalues.values() and jointfapvalues.values()), idqthresh))
                event_dict['idq_joint_fapCheckresult'] = False
               # g.writeLabel(graceid, 'DQV')
                return False
        elif (len(idqvalues) > (len(idq_pipelines)*len(instruments))):
            logger.info('{0} -- {1} -- Too many minfap values in idqvalues dictionary.'.format(convertTime(), graceid))
        else:
            logger.info('{0} -- {1} -- Ready to run iDQ checks.'.format(convertTime(), graceid))
            # 'glitch-FAP' is the probabilty that the classifier thinks there was a glitch and there was not a glitch
            # 'glitch-FAP' -> 0 means high confidence that there is a glitch
            # 'glitch-FAP' -> 1 means low confidence that there is a glitch
            # What we want is the minimum of the products of FAPs from different sites computed for each classifier
            for idqpipeline in idq_pipelines:
                jointfap = 1
                for idqdetector in instruments:
                    detectorstring = '{0}.{1}'.format(idqpipeline, idqdetector)
                    jointfap = jointfap*idqvalues[detectorstring]
                jointfapvalues[idqpipeline] = jointfap
                logger.info('{0} -- {1} -- Got joint_fap = {2} for iDQ pipeline {3}.'.format(convertTime(), graceid, jointfap, idqpipeline))
            if min(jointfapvalues.values()) > idqthresh:
                if idqlogkey=='no':
                   # g.writeLog(graceid, 'AP: Finished running iDQ checks. Candidate event passed iDQ checks. {0} > {1}'.format(min(jointfapvalues.values()), idqthresh), tagname = 'em_follow')
                    event_dict['idqlogkey']='yes'
                logger.info('{0} -- {1} -- Passed iDQ check: {2} > {3}.'.format(convertTime(), graceid, min(jointfapvalues.values()), idqthresh))
                event_dict['idq_joint_fapCheckresult'] = True
                return True
            else:
                if idqlogkey=='no':
                   # g.writeLog(graceid, 'AP: Finished running iDQ checks. Candidate event rejected due to low iDQ FAP value. {0} < {1}'.format(min(jointfapvalues.values()), idqthresh), tagname = 'em_follow')
                    event_dict['idqlogkey'] = 'yes'
                logger.info('{0} -- {1} -- Failed iDQ check: {2} < {3}. Labeling DQV.'.format(convertTime(), graceid, min(jointfapvalues.values()), idqthresh))
                event_dict['idq_joint_fapCheckresult'] = False
               # g.writeLabel(graceid, 'DQV')
                return False

#-----------------------------------------------------------------------
# operator_signoffCheck
#-----------------------------------------------------------------------
def record_signoff(event_dict, signoff_object):
    instrument = signoff_object['instrument']
    signofftype = signoff_object['signoff_type']
    status = signoff_object['status']
    if signofftype=='OP':
        operatorsignoffs = event_dict['operatorsignoffs']
        operatorsignoffs[instrument] = status
    if signofftype=='ADV':
        advocatesignoffs = event_dict['advocatesignoffs']
        advocatesignoffs.append(status)

def operator_signoffCheck(event_dict):
    operator_signoffCheckresult = event_dict['operator_signoffCheckresult']
    if operator_signoffCheckresult!=None:
        return operator_signoffCheckresult
    else:
        graceid = event_dict['graceid']
        instruments = event_dict['instruments']
        operatorlogkey = event_dict['operatorlogkey']
        operatorsignoffs = event_dict['operatorsignoffs']
        if len(operatorsignoffs) < len(instruments):
            if 'NO' in operatorsignoffs.values():
                if operatorlogkey=='no':
                    logger.info('{0} -- {1} -- Candidate event failed operator signoff check. Labeling DQV.'.format(convertTime(), graceid))
                   # g.writeLog(graceid, 'AP: Candidate event failed operator signoff check.', tagname = 'em_follow')
                    event_dict['operatorlogkey'] = 'yes'
                   # g.writeLabel(graceid, 'DQV')
                event_dict['operator_signoffCheckresult'] = False
                return False
            else:
                logger.info('{0} -- {1} -- Not all operators have signed off yet.'.format(convertTime(), graceid))
        else:
            if 'NO' in operatorsignoffs.values():
                if operatorlogkey=='no':
                    logger.info('{0} -- {1} -- Candidate event failed operator signoff check. Labeling DQV.'.format(convertTime(), graceid))
                   # g.writeLog(graceid, 'AP: Candidate event failed operator signoff check.', tagname = 'em_follow')
                    event_dict['operatorlogkey'] = 'yes'
                   # g.writeLabel(graceid, 'DQV')
                event_dict['operator_signoffCheckresult'] = False
                return False
            else:
                if operatorlogkey=='no':
                    logger.info('{0} -- {1} -- Candidate event passed operator signoff check.'.format(convertTime(), graceid))
                   # g.writeLog(graceid, 'AP: Candidate event passed operator signoff check.', tagname = 'em_follow')
                    event_dict['operatorlogkey'] = 'yes'
                event_dict['operator_signoffCheckresult'] = True
                return True

#-----------------------------------------------------------------------
# advocate_signoffCheck
#-----------------------------------------------------------------------
def advocate_signoffCheck(event_dict):
    advocate_signoffCheckresult = event_dict['advocate_signoffCheckresult']
    if advocate_signoffCheckresult!=None:
        return advocate_signoffCheckresult
    else:
        advocatelogkey = event_dict['advocatelogkey']
        advocatesignoffs = event_dict['advocatesignoffs']
        graceid = event_dict['graceid']
        if len(advocatesignoffs)==0:
            logger.info('{0} -- {1} -- Advocates have not signed off yet.'.format(convertTime(), graceid))
        elif len(advocatesignoffs) > 0:
            if 'NO' in advocatesignoffs:
                if advocatelogkey=='no':
                    logger.info('{0} -- {1} -- Candidate event failed advocate signoff check. Labeling DQV.'.format(convertTime(), graceid))
                   # g.writeLog(graceid, 'AP: Candidate event failed advocate signoff check.', tagname = 'em_follow')
                    event_dict['advocatelogkey'] = 'yes'
                   # g.writeLabel(graceid, 'DQV')
                event_dict['advocate_signoffCheckresult'] = False
                return False
            else:
                if advocatelogkey=='no':
                    logger.info('{0} -- {1} -- Candidate event passed advocate signoff check.'.format(convertTime(), graceid))
                   # g.writeLog(graceid, 'AP: Candidate event passed advocate signoff check.', tagname = 'em_follow')
                    event_dict['advocatelogkey'] = 'yes'
                event_dict['advocate_signoffCheckresult'] = True
                return True
        
#-----------------------------------------------------------------------
# process_alert
#-----------------------------------------------------------------------
def process_alert(event_dict, voevent_type):
    graceid = event_dict['graceid']
    pipeline = event_dict['pipeline']
    voeventerrors = sorted(event_dict['voeventerrors'])
    voevents = sorted(event_dict['voevents'])

    # check if we just sent this voevent
    if (voevent_type in voevents[-1]):
        return
    else:
        pass

    # setting default internal value settings for alerts
    if force_all_internal=='yes':
        internal = 1
    else:
        internal = 0

    if voevent_type=='preliminary':
        if force_all_internal=='yes':
            internal = 1
        else:
            if pipeline in preliminary_internal:
                internal = 1
            else:
                internal = 0
        skymap_filename = None
        skymap_type = None
        skymap_image_filename = None

    if voevent_type=='retraction':
        # check if we've sent alerts for this event
        if len(voevents) > 0:
            # check if we sent a retraction alert before:
            for voevent in voevents:
                if voevent_type in voevent:
                    return
            # there are existing alerts but we haven't sent a retraction so let's do that
            if (force_all_internal!='yes') and (pipeline in preliminary_internal):
                lastvoeventsent = voevents[-1]
                if 'preliminary' in lastvoeventsent:
                    internal = 1
                else:
                    internal = 0
            else:
                pass
        skymap_filename = None
        skymap_type = None
        skymap_image_filename = None

    if (voevent_type=='initial' or voevent_type=='update'):
        skymap_filename = current_lvem_skymap(event_dict)
        if skymap_filename==None:
            skymap_type = None
            skymap_image_filename = None
        else:
            skymapname = re.findall(r'(\S+).fits', skymap_filename)[0]
            group = event_dict['group']
            search = event_dict['search']
            skymap_type = skymapname + '-' + group + search
            skymap_image_filename = skymapname + '.png'
            #submitter = event_dict['lvemskymaps'][skymap_filename]

    injectionsfound = event_dict['injectionsfound']
    if injectionsfound==None:
        injectionCheck(event_dict)
        injection = event_dict['injectionsfound']
    else:
        injection = injectionsfound

    logger.info('{0} -- {1} -- Creating {2} VOEvent file locally.'.format(convertTime(), graceid, voevent_type))
    voevent = None
    try:
        r = g.createVOEvent(graceid, voevent_type, skymap_filename = skymap_filename, skymap_type = skymap_type, skymap_image_filename = skymap_image_filename, internal = internal)
        voevent = r.json()['text']
    except Exception, e:
        logger.info('{0} -- {1} -- Caught HTTPError: {2}'.format(convertTime(), graceid, str(e)))
    number = str(random.random())
    if voevent:
        tmpfile = open('/tmp/voevent_{0}_{1}.tmp'.format(graceid, number), 'w')
        tmpfile.write(voevent)
        tmpfile.close()
        cmd = 'comet-sendvo -p 5340 -f /tmp/voevent_{0}_{1}.tmp'.format(graceid, number)
        proc = sp.Popen(cmd, shell = True, stdout = sp.PIPE, stderr = sp.PIPE)
        output, error = proc.communicate(voevent)
        thisvoevent = '{0}-(internal,injection):({1},{2})-'.format(len(voevents), internal, injection) + voevent_type
        if proc.returncode==0:
            message = '{0} VOEvent sent to GCN.'.format(voevent_type)
            voevents.append(thisvoevent)
            for key in voeventerrors:
                if voevent_type in key:
                    voeventerrors.remove(key)
            if (voevent_type=='initial' or voevent_type=='update'):
                event_dict['lastsentskymap'] = skymap_filename
            else:
                pass
        else:
            message = 'Error sending {0} VOEvent! {1}.'.format(voevent_type, error)
            g.writeLog(graceid, 'AP: Could not send VOEvent type {0}.'.format(voevent_type), tagname = 'em_follow')
            listofvoeventerrors = ''
            for i in range(0, len(list)):
                listofvoeventerrors += '{0} '.format(list[i])
            if voevent_type in listofvoeventerrors:
                pass
            else:
                os.system('echo \'{0}\' | mail -s \'Problem sending {1} VOEvent: {2}\' {3}'.format(message, graceid, voevent_type, voeventerror_email))
                voeventerrors.append(thisvoevent)
        logger.info('{0} -- {1} -- {2}'.format(convertTime(), graceid, message))
        os.remove('/tmp/voevent_{0}_{1}.tmp'.format(graceid, number))
