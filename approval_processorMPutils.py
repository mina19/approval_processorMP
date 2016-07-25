description = "utilities for approval_processorMP.py"
author = "Min-A Cho (mina19@umd.edu), Reed Essick (reed.essick@ligo.org)"

#-----------------------------------------------------------------------
# Import packages
#-----------------------------------------------------------------------

from queueItemsAndTasks import * ### DANGEROUS! but should be ok here...

from ligoMP.lvalert import lvalertMPutils as utils
from ligo.gracedb.rest import GraceDb, HTTPError

import os
import json
import pickle
import urllib
import logging

import ConfigParser

import time
import datetime

import subprocess as sp

import re

import operator

import functools

import random

#-----------------------------------------------------------------------
# Activate a virtualenv in order to be able to use Comet.
#-----------------------------------------------------------------------

VIRTUALENV_ACTIVATOR = "/home/alexander.pace/emfollow_gracedb/cometenv/bin/activate_this.py"
execfile(VIRTUALENV_ACTIVATOR, dict(__file__=VIRTUALENV_ACTIVATOR))

#-----------------------------------------------------------------------
# Creating event dictionaries
#-----------------------------------------------------------------------
global eventDicts # global variable for local bookkeeping of event candidate checks, files, labels, etc.
eventDicts = {} # it's a dictionary storing data in the form 'graceid': event_dict where each event_dict is created below in class EventDict

### instantionation and createDict methods seem like their input arguments should be reversed...

class EventDict:
    '''
    creates an event_dict for each event candidate to keep track of checks, files, comments, labels coming in
    '''
    def __init__(self, dictionary, graceid, configdict):
        self.dictionary = dictionary ### a dictionary either extracted from a lvalert or from a call to ligo.gracedb.rest.GraceDb.event(self.graceid)
        self.graceid    = graceid
        self.configdict = configdict ### stores settings used 

    def createDict(self):
        '''
        creates an event_dict for event candidate with self.graceid in the currentstate 'new_to_preliminary'
        '''
        eventDicts[self.graceid] = {
            'advocate_signoffCheckresult': None,
            'advocatelogkey'             : 'no',
            'advocatesignoffs'           : [],
            'configuration'              : self.configdict,
            'currentstate'               : 'new_to_preliminary',
            'far'                        : self.dictionary['far'],
            'farCheckresult'             : None,
            'farlogkey'                  : 'no',
            'expirationtime'             : None,
            'gpstime'                    : float(self.dictionary['gpstime']),
            'graceid'                    : self.graceid,
            'group'                      : self.dictionary['group'],
            'have_lvem_skymapCheckresult': None,
            'idq_joint_fapCheckresult'   : None,
            'idqlogkey'                  : 'no',
            'idqvalues'                  : {},
            'injectionCheckresult'       : None,
            'injectionsfound'            : None,
            'injectionlogkey'            : 'no',
            'instruments'                : str(self.dictionary['instruments']).split(','),
            'jointfapvalues'             : {},
            'labelCheckresult'           : None,
            'labels'                     : self.dictionary['labels'].keys(),
            'lastsentskymap'             : None,
            'loggermessages'             : [],
            'lvemskymaps'                : {},
            'operator_signoffCheckresult': None,
            'operatorlogkey'             : 'no',
            'operatorsignoffs'           : {},
            'pipeline'                   : self.dictionary['pipeline'],
            'search'                     : self.dictionary['search'] if self.dictionary.has_key('search') else '',
            'voeventerrors'              : [],
            'voevents'                   : [],
        }

#-----------------------------------------------------------------------
# Saving event dictionaries
#-----------------------------------------------------------------------
def saveEventDicts():
    '''
    saves eventDicts (the dictonary of event dictionaries) to a pickle file and txt file
    '''

    ### figure out filenames, etc.
    ### FIXME: THIS SHOULD NOT BE HARD CODED! Instead, use input arguments
    homedir = os.path.expanduser('~')
    pklfilename = '{0}/public_html/monitor/approval_processorMP/files/EventDicts.p'.format(homedir)
    txtfilename = '{0}/public_html/monitor/approval_processorMP/files/EventDicts.txt'.format(homedir)

    ### write pickle file
    file_obj = open(pklfilename, 'wb')
    pickle.dump(eventDicts, file_obj)
    file_obj

    ### write txt file
    file_obj = open(txtfilename, 'w')
    for graceid in sorted(eventDicts.keys()): ### iterate through graceids
        file_obj.write('{0}\n'.format(graceid))
        event_dict = eventDicts[graceid]

        for key in sorted(event_dict.keys()): ### iterate through keys for this graceid
            if key!='loggermessages':
                file_obj.write('    {0}: {1}\n'.format(key, event_dict[key]))
        file_obj.write('\n')
    file_obj.close()

#-----------------------------------------------------------------------
# Loading event dictionaries
#-----------------------------------------------------------------------
def loadEventDicts():
    '''
    loads eventDicts (the dictionary of event dictionaries) to do things like resend VOEvents for an event candidate
    '''
    ### figure out filenames
    ### FIXME: THIS SHOULD NOT BE HARD CODED! Instead, use input arguments
    homedir = os.path.expanduser('~')
    pklname = '{0}/public_html/monitor/approval_processorMP/files/EventDicts.p'.format(homedir)

    if os.path.exists(pklname): ### check to see if the file actually exists
        file_obj = open(pklname, 'rb')
        global eventDicts
        eventDicts = pickle.load(file_obj) ### if something fails here, we want to know about it!
        file_obj.close()

#-----------------------------------------------------------------------
# parseAlert
#-----------------------------------------------------------------------
def parseAlert(queue, queueByGraceID, alert, t0, config):
    '''
    the way approval_processorMP digests lvalerts
    1) instantiates GraceDB client
    2) pulls childConfig settings
    3) makes sure we have the logger
    4) get lvalert specifics
    5) ensure we have the event_dict for the graceid = lvalert['uid']
    6) take proper action depending on the lvalert info coming in and currentstate of the event_dict 
    '''
    #-------------------------------------------------------------------
    # extract relevant config parameters and set up necessary data structures
    #-------------------------------------------------------------------

    # instantiate GraceDB client from the childConfig
    client = config.get('general', 'client')
    g = GraceDb(client)

    # get other childConfig settings; save in configdict
    voeventerror_email   = config.get('general', 'voeventerror_email')
    force_all_internal   = config.get('general', 'force_all_internal')
    preliminary_internal = config.get('general', 'preliminary_internal')
    forgetmenow_timeout  = config.getfloat('general', 'forgetmenow_timeout')
    hardware_inj         = config.get('labelCheck', 'hardware_inj')
    default_farthresh    = config.getfloat('farCheck', 'default_farthresh')
    time_duration        = config.getfloat('injectionCheck', 'time_duration')
    humanscimons         = config.get('operator_signoffCheck', 'humanscimons')

    ### extract options about advocates
    advocates      = config.get('advocate_signoffCheck', 'advocates')
    advocate_text  = config.get('advocate_signoffCheck', 'advocate_text')
    advocate_email = config.get('advocate_signoffCheck', 'advocate_email')

    ### extract options about idq
    ignore_idq        = config.get('idq_joint_fapCheck', 'ignore_idq')
    default_idqthresh = config.getfloat('idq_joint_fapCheck', 'default_idqthresh')
    idq_pipelines     = config.get('idq_joint_fapCheck', 'idq_pipelines')
    idq_pipelines     = idq_pipelines.replace(' ','')
    idq_pipelines     = idq_pipelines.split(',')

    skymap_ignore_list = config.get('have_lvem_skymapCheck', 'skymap_ignore_list')

    ### set up configdict (passed to local data structure: eventDicts)
    configdict = {
        'force_all_internal'  : force_all_internal,
        'preliminary_internal': preliminary_internal,
        'hardware_inj'        : hardware_inj,
        'default_farthresh'   : default_farthresh,
        'humanscimons'        : humanscimons,
        'advocates'           : advocates,
        'ignore_idq'          : ignore_idq,
        'default_idqthresh'   : default_idqthresh,
    }

    # set up logging
    ### FIXME: why not open the logger each time parseAlert is called?
    ###        that would allow you to better control which loggers are necessary and minimize the number of open files.
    ###        it also minimizes the possibility of something accidentally being written to loggers because they were left open.
    ###        what's more, this is a natural place to set up multiple loggers, one for all data and one for data pertaining only to this graceid

    global logger
    try: 
        logger  ### FIXME: why not open the logger each time parseAlert is called?
    except NameError:
        logger = logging.getLogger('approval_processorMP')
        logfile = config.get('general', 'approval_processorMP_logfile')
        homedir = os.path.expanduser('~')
        logging_filehandler = logging.FileHandler('{0}/public_html/monitor/approval_processorMP/files{1}'.format(homedir, logfile))
        logging_filehandler.setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
        logger.addHandler(logging_filehandler)
        logger.info('\n{0} ************ approval_processorMP.log RESTARTED ************\n'.format(convertTime())) ### this information seems to be the only useful bit.

    #-------------------------------------------------------------------
    # extract relevant info about this alert
    #-------------------------------------------------------------------

    # get alert specifics and event_dict information
    graceid     = alert['uid']
    alert_type  = alert['alert_type']
    description = alert['description']
    filename    = alert['file']

    #-------------------------------------------------------------------
    # ensure we have an event_dict and ForgetMeNow tracking this graceid
    #-------------------------------------------------------------------

    if alert_type=='new': ### new event -> we must first create event_dict and set up ForgetMeNow queue item

        ### create event_dict
        EventDict( alert['object'], graceid, configdict ).createDict() # create event_dict for event candidate
        event_dict = eventDicts[graceid] # get event_dict with expirationtime key updated for the rest of parseAlert

        ### create ForgetMeNow queue item
        item = ForgetMeNow( t0, forgetmenow_timeout, graceid, eventDicts, queue, queueByGraceID, logger)
        queue.insert(item) # add queue item to the overall queue

        ### set up queueByGraceID
        newSortedQueue = utils.SortedQueue() # create sorted queue for event candidate
        newSortedQueue.insert(item) # put ForgetMeNow queue item into the sorted queue
        queueByGraceID[item.graceid] = newSortedQueue # add queue item to the queueByGraceID

        message = '{0} -- {1} -- Created event dictionary for {1}.'.format(convertTime(), graceid)
        if loggerCheck(event_dict, message)==False: ### FIXME? Reed still isn't convinced 'loggerCheck' is a good idea and thinks we should just print everything, always. ### Mina disagrees here; without the loggerCheck there are sometimes the same messages printed ten, twenty times but out of order. very hard to read the logger and understand the event candidate
            logger.info(message)
        else:
            pass

    else: ### not a new alert -> we may already be tracking this graceid

        if eventDicts.has_key(graceid): ### we're already tracking it

            # get event_dict with expirationtime key updated for the rest of parseAlert
            event_dict = eventDicts[graceid]

            # find ForgetMeNow corresponding to this graceid and update expiration time
            for item in queueByGraceID[graceid]:
                if item.name==ForgetMeNow.name: # selects the queue item that is a ForgetMeNow instance
                    item.setExpiration(t0, convertTime) # updates the expirationtime key
                    break
            else: ### we couldn't find a ForgetMeNow for this event! Something is wrong!
                os.system('echo \'ForgetMeNow KeyError\' | mail -s \'ForgetMeNow KeyError {0}\' {1}'.format(graceid, advocate_email))       
                raise KeyError('could not find ForgetMeNow for %s'%graceid) ### Reed thinks this is necessary as a safety net. 
                                                                            ### we want the process to terminate if things are not set up correctly to force us to fix it

        else: # event_dict for event candidate does not exist. we need to create it with up-to-date information

            # query gracedb to get information
            EventDict( g.events(graceid).next(), graceid, configdict ).createDict()
            event_dict = eventDicts[graceid]

            # update signoff information if available
            url = g.templates['signoff-list-template'].format(graceid=graceid) # construct url for the operator/advocate signoff list
            signoff_list = g.get(url).json()['signoff'] # pull down signoff list
            for signoff_object in signoff_list:
                record_signoff(eventDicts[graceid], signoff_object)

            # update iDQ information if available
            log_dicts = g.logs(graceid).json()['log']
            for message in log_dicts:
                if re.match('minimum glitch-FAP', message['comment']):
                    record_idqvalues(eventDicts[graceid], message['comment'], logger)
                else:
                    pass

            # create ForgetMeNow queue item and add to overall queue and queueByGraceID
            item = ForgetMeNow(t0, forgetmenow_timeout, graceid, eventDicts, queue, queueByGraceID, logger)
            queue.insert(item) # add queue item to the overall queue

            ### set up queueByGraceID
            newSortedQueue = utils.SortedQueue() # create sorted queue for new event candidate
            newSortedQueue.insert(item) # put ForgetMeNow queue item into the sorted queue
            queueByGraceID[item.graceid] = newSortedQueue # add queue item to the queueByGraceID

            message = '{0} -- {1} -- Created event dictionary for {1}.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass

    saveEventDicts() ### save dicts to make sure copy on disk stays up to date
                     ### FIXME? Reed's not sure if we need to do this here. We probably don't want to write out the dicts more than once each time parseAlert is called...

    #--------------------
    # ignore alerts that are not relevant, like simulation or MDC events
    #--------------------

    # if the graceid starts with 'M' for MDCs or 'S' for Simulation, ignore
    if re.match('M', graceid) or re.match('S', graceid): ### FIXME: we want to make this a config-file option!
        message = '{0} -- {1} -- Mock data challenge or simulation. Ignoring.'.format(convertTime(), graceid)
        if loggerCheck(event_dict, message)==False:
            logger.info(message)
        else:
            pass
        return 0

    #--------------------
    # Definitions of which checks must be satisfied in each state before moving on
    # FIXME: can we define these (once) outside of parseAlert instead of re-defining them each time it is called?
    #--------------------

    # tasks when currentstate of event is new_to_preliminary
    new_to_preliminary = [
        'farCheck',
        'labelCheck',
        'injectionCheck'
        ]

    # tasks when currentstate of event is preliminary_to_initial
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

    # tasks when currentstate of event is initial_to_update
    initial_to_update = [
        'farCheck',
        'labelCheck',
        'have_lvem_skymapCheck'
        ]

    #--------------------
    # update information based on the alert_type
    # includes extracting information from the alert
    # may also include generating VOEvents and issuing them
    #--------------------

    ### FIXME: Reed left off commenting here...

    # actions for each alert_type
    currentstate = event_dict['currentstate']

    if alert_type=='label':
        record_label(event_dict, description)
        saveEventDicts()
        if description=='PE_READY':
            message = '{0} -- {1} -- Sending update VOEvent.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                process_alert(event_dict, 'update', g, config, logger)
            else:
                pass
            message = '{0} -- {1} -- State: {2} --> complete.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                event_dict['currentstate'] = 'complete'
            else:
                pass
        elif description=='EM_READY':
            message = '{0} -- {1} -- Sending initial VOEvent.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                process_alert(event_dict, 'initial', g, config, logger)
            else:
                pass
            message = '{0} -- {1} -- State: {2} --> initial_to_update.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                event_dict['currentstate'] = 'initial_to_update'
            else:
                pass

        elif (checkLabels(description.split(), config) > 0):
            event_dict['currentstate'] = 'rejected'
            voevents = sorted(event_dict['voevents'])
            if len(voevents) > 0:
                if 'retraction' in voevents[-1]:
                    return 0
                # there are existing VOEvents we've sent, but no retraction alert
                process_alert(event_dict, 'retraction', g, config, logger)
        saveEventDicts()
        return 0

    if alert_type=='update':
        # first the case that we have a new lvem skymap
        if (filename.endswith('.fits.gz') or filename.endswith('.fits')):
            if 'lvem' in alert['object']['tag_names']:
                submitter = alert['object']['issuer']['display_name']
                record_skymap(event_dict, filename, submitter, logger)
            else:
                pass
        # interested in iDQ information
        else:
            if 'comment' in alert['object'].keys():
                comment = alert['object']['comment']
                if re.match('minimum glitch-FAP', comment):
                    record_idqvalues(event_dict, comment, logger)
                elif re.match('resent VOEvent', comment):
                    response = re.findall(r'resent VOEvent (.*) in (.*)', comment)
                    event_dict[response[0][1]].append(response[0][0])
                    saveEventDicts()
                else:
                    pass

    if alert_type=='signoff':
        signoff_object = alert['object']
        record_signoff(event_dict, signoff_object)

    # run checks specific to currentstate of the event candidate
    passedcheckcount = 0

    if currentstate=='new_to_preliminary':
        for Check in new_to_preliminary:
            eval('{0}(event_dict, g, config, logger)'.format(Check))
            checkresult = event_dict[Check + 'result']
            if checkresult==None:
                pass
            elif checkresult==False:
                # because in 'new_to_preliminary' state, no need to apply DQV label
                message = '{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                else:
                    pass
                message = '{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['currentstate'] = 'rejected'
                else:
                    pass
                saveEventDicts()
                return 0
            elif checkresult==True:
                passedcheckcount += 1
        if passedcheckcount==len(new_to_preliminary):
            message = '{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
            message = '{0} -- {1} -- Sending preliminary VOEvent.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                process_alert(event_dict, 'preliminary', g, config, logger)
            else:
                pass
            message = '{0} -- {1} -- State: {2} --> preliminary_to_initial.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                event_dict['currentstate'] = 'preliminary_to_initial'
            else:
                pass
            # notify the operators
            instruments = event_dict['instruments']
            for instrument in instruments:
                message = '{0} -- {1} -- Labeling {2}OPS.'.format(convertTime(), graceid, instrument)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    g.writeLabel(graceid, '{0}OPS'.format(instrument))
                else:
                    pass
            # notify the advocates
            message = '{0} -- {1} -- Labeling ADVREQ.'.format(convertTime(), graceid, instrument)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                g.writeLabel(graceid, 'ADVREQ')
                os.system('echo \'{0}\' | mail -s \'{1} passed criteria for follow-up\' {2}'.format(advocate_text, graceid, advocate_email))
                # expose event to LV-EM
                url_perm_base = g.service_url + urllib.quote('events/{0}/perms/gw-astronomy:LV-EM:Observers/'.format(graceid))
                for perm in ['view', 'change']:
                    url = url_perm_base + perm
                    #g.put(url)
            else:
                pass
        saveEventDicts()
        return 0

    elif currentstate=='preliminary_to_initial':
        for Check in preliminary_to_initial:
            eval('{0}(event_dict, g, config, logger)'.format(Check))
            checkresult = event_dict[Check + 'result']
            if checkresult==None:
                pass
            elif checkresult==False:
               # need to set DQV label
                message = '{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                else:
                    pass
                message = '{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['currentstate'] = 'rejected'
                else:
                    pass
                message = '{0} -- {1} -- Labeling DQV.'.format(convertTime(), graceid)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    g.writeLabel(graceid, 'DQV')
                else:
                    pass
                saveEventDicts()
                return 0
            elif checkresult==True:
                passedcheckcount += 1
        if passedcheckcount==len(preliminary_to_initial):
            message = '{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
            message = '{0} -- {1} -- Labeling EM_READY.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                g.writeLabel(graceid, 'EM_READY')
            else:
                pass
        saveEventDicts()
        return 0

    elif currentstate=='initial_to_update':
        for Check in initial_to_update:
            eval('{0}(event_dict, g, config, logger)'.format(Check))
            checkresult = event_dict[Check + 'result']
            if checkresult==None:
                pass
            elif checkresult==False:
               # need to set DQV label
                message = '{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                else:
                    pass
                message = '{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['currentstate'] = 'rejected'
                else:
                    pass
                message = '{0} -- {1} -- Labeling DQV.'.format(convertTime(), graceid)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    g.writeLabel(graceid, 'DQV')
                else:
                    pass
                saveEventDicts()
                return 0
            elif checkresult==True:
                passedcheckcount += 1
        if passedcheckcount==len(initial_to_update):
            message = '{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
            message = '{0} -- {1} -- Labeling PE_READY.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                g.writeLabel(graceid, 'PE_READY')
            else:
                pass
        saveEventDicts()
        return 0
    
    else:
        return 0

#-----------------------------------------------------------------------
# Utilities
#-----------------------------------------------------------------------
def convertTime(ts=None):
    if ts is None:
        ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return st

def loggerCheck(event_dict, message):
    loggermessages = event_dict['loggermessages']
    graceid = event_dict['graceid']
    message = re.findall(r'-- {0} -- (.*)'.format(graceid), message)[0]
    if message in loggermessages:
        return True
    else:
        event_dict['loggermessages'].append(message)
        return False
    
#-----------------------------------------------------------------------
# farCheck
#-----------------------------------------------------------------------
def get_farthresh(pipeline, search, config):
    try:
        return config.getfloat('farCheck', 'farthresh[{0}.{1}]'.format(pipeline, search))
    except:
        return config.getfloat('farCheck', 'default_farthresh')

def farCheck(event_dict, client, config, logger):
    farCheckresult = event_dict['farCheckresult']
    if farCheckresult!=None:
        return farCheckresult
    else:
        far = event_dict['far']
        graceid = event_dict['graceid']
        pipeline = event_dict['pipeline']
        search = event_dict['search']
        farthresh = get_farthresh(pipeline, search, config)
        if far >= farthresh:
            client.writeLog(graceid, 'AP: Candidate event rejected due to large FAR. {0} >= {1}'.format(far, farthresh), tagname='em_follow')
            event_dict['farlogkey'] = 'yes'
            message = '{0} -- {1} -- Rejected due to large FAR. {2} >= {3}'.format(convertTime(), graceid, far, farthresh)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                event_dict['farCheckresult'] = False
            else:
                pass
            return False
        elif far < farthresh:
            client.writeLog(graceid, 'AP: Candidate event has low enough FAR.{0} < {1}'.format(far, farthresh), tagname='em_follow')
            event_dict['farlogkey'] = 'yes'
            message = '{0} -- {1} -- Low enough FAR. {2} < {3}'.format(convertTime(), graceid, far, farthresh)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                event_dict['farCheckresult'] = True
            else:
                pass
            return True

#-----------------------------------------------------------------------
# labelCheck
#-----------------------------------------------------------------------
def checkLabels(labels, config):
    hardware_inj = config.get('labelCheck', 'hardware_inj')
    if hardware_inj == 'yes':
        badlabels = ['DQV']
    else:
        badlabels = ['DQV', 'INJ']
    intersectionlist = list(set(badlabels).intersection(labels))
    return len(intersectionlist)

def labelCheck(event_dict, client, config, logger):
    graceid = event_dict['graceid']
    labels = event_dict['labels']
    if checkLabels(labels, config) > 0:
        message = '{0} -- {1} -- Ignoring event due to INJ or DQV label.'.format(convertTime(), graceid)
        if loggerCheck(event_dict, message)==False:
            logger.info(message)
            event_dict['labelCheckresult'] = False
        else:
            pass
        return False
    else:
        event_dict['labelCheckresult'] = True
        return True

def record_label(event_dict, label):
    labels = event_dict['labels']
    graceid = event_dict['graceid']
    labels.append(label)
    message = '{0} -- {1} -- Got {2} label.'.format(convertTime(), graceid, label)
    if loggerCheck(event_dict, message)==False:
        logger.info(message)
    else:
        pass

#-----------------------------------------------------------------------
# injectionCheck
#-----------------------------------------------------------------------
def injectionCheck(event_dict, client, config, logger):
    injectionCheckresult = event_dict['injectionCheckresult']
    if injectionCheckresult!=None:
        return injectionCheckresult
    else:
        eventtime = float(event_dict['gpstime'])
        graceid = event_dict['graceid']
        time_duration = config.getfloat('injectionCheck', 'time_duration')
        from raven.search import query
        th = time_duration
        tl = -th
        Injections = query('HardwareInjection', eventtime, tl, th)
        event_dict['injectionsfound'] = len(Injections)
        hardware_inj = config.get('labelCheck', 'hardware_inj')
        if len(Injections) > 0:
            if hardware_inj=='no':
                client.writeLog(graceid, 'AP: Ignoring new event because we found a hardware injection +/- {0} seconds of event gpstime.'.format(th), tagname = "em_follow")
                event_dict['injectionlogkey'] = 'yes'
                message = '{0} -- {1} -- Ignoring new event because we found a hardware injection +/- {2} seconds of event gpstime.'.format(convertTime(), graceid, th)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['injectionCheckresult'] = False
                else:
                    pass
                return False
            else:
                client.writeLog(graceid, 'AP: Found hardware injection +/- {0} seconds of event gpstime but treating as real event in config.'.format(th), tagname = "em_follow")
                event_dict['injectionlogkey'] = 'yes'
                message = '{0} -- {1} -- Found hardware injection +/- {2} seconds of event gpstime but treating as real event in config.'.format(convertTime(), graceid, th)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['injectionCheckresult'] = True
                else:
                    pass
                return True
        elif len(Injections)==0:
            client.writeLog(graceid, 'AP: No hardware injection found near event gpstime +/- {0} seconds.'.format(th), tagname="em_follow")
            event_dict['injectionlogkey'] = 'yes'
            message = '{0} -- {1} -- No hardware injection found near event gpstime +/- {2} seconds.'.format(convertTime(), graceid, th)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
                event_dict['injectionCheckresult'] = True
            else:
                pass
            return True

#-----------------------------------------------------------------------
# have_lvem_skymapCheck
#-----------------------------------------------------------------------
def have_lvem_skymapCheck(event_dict, client, config, logger):
    # this function should only return True or None, never False
    # if return True, we have a new lvem skymap
    # otherwise, add this Check to queueByGraceID
    graceid = event_dict['graceid']
    currentstate = event_dict['currentstate']
    lvemskymaps = event_dict['lvemskymaps'].keys()

    if currentstate=='preliminary_to_initial':
        if len(lvemskymaps)>=1:
            event_dict['have_lvem_skymapCheckresult'] = True
            skymap = sorted(lvemskymaps)[-1]
            skymap = re.findall(r'-(\S+)', skymap)[0]
            message = '{0} -- {1} -- Initial skymap tagged lvem {2} available.'.format(convertTime(), graceid, skymap)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
            return True
        else:
            event_dict['have_lvem_skymapCheckresult'] = None
            return None

    elif (currentstate=='initial_to_update' or currentstate=='complete'):
        if len(lvemskymaps)>=2:
            if lvemskymaps[-1]!=event_dict['lastsentskymap']:
                event_dict['have_lvem_skymapCheckresult'] = True
                skymap = sorted(lvemskymaps)[-1]
                skymap = re.findall(r'-(\S+)', skymap)[0]
                message = '{0} -- {1} -- Update skymap tagged lvem {2} available.'.format(convertTime(), graceid, skymap)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                else:
                    pass
                return True
            else:
                event_dict['have_lvem_skymapCheckresult'] = None
                return None
        else:
            event_dict['have_lvem_skymapCheckresult'] = None
            return None

def current_lvem_skymap(event_dict):
    lvemskymaps = sorted(event_dict['lvemskymaps'].keys())
    if len(lvemskymaps)==0:
        return None
    else:
        skymap = sorted(lvemskymaps)[-1]
        skymap = re.findall(r'-(\S+)', skymap)[0]
        return skymap

def record_skymap(event_dict, skymap, submitter, logger):
    # this only records skymaps with the lvem tag
    graceid = event_dict['graceid']
    lvemskymaps = sorted(event_dict['lvemskymaps'].keys())
    currentnumber = len(lvemskymaps) + 1
    skymapkey = '{0}'.format(currentnumber) + '-'+ skymap
    # check if we already have the skymap
    count = 0
    for map in lvemskymaps:
        if skymap in map:
            count += 1
        else:
            count +=0
    if count==0:
        event_dict['lvemskymaps'][skymapkey] = submitter
        message = '{0} -- {1} -- Got the lvem skymap {2}.'.format(convertTime(), graceid, skymap)
        if loggerCheck(event_dict, message)==False:
            logger.info(message)
        else:
            pass

#-----------------------------------------------------------------------
# idq_joint_fapCheck
#-----------------------------------------------------------------------
def get_idqthresh(pipeline, search, config):
    try:
        return config.getfloat('idq_joint_fapCheck', 'idqthresh[{0}.{1}]'.format(pipeline, search))
    except:
        return config.getfloat('idq_joint_fapCheck', 'default_idqthresh')

def record_idqvalues(event_dict, comment, logger):
    graceid = event_dict['graceid']
    idqinfo = re.findall('minimum glitch-FAP for (.*) at (.*) with', comment)
    idqpipeline = idqinfo[0][0]
    idqdetector = idqinfo[0][1]
    minfap = re.findall('is (.*)', comment)
    minfap = float(minfap[0])
    detectorstring = '{0}.{1}'.format(idqpipeline, idqdetector)
    event_dict['idqvalues'][detectorstring] = minfap    
    message = '{0} -- {1} -- Got the minfap for {2} using {3} is {4}.'.format(convertTime(), graceid, idqdetector, idqpipeline, minfap)
    if loggerCheck(event_dict, message)==False:
        logger.info(message)
    else:
        pass

def compute_joint_fap_values(event_dict, config):
    idqvalues = event_dict['idqvalues']
    jointfapvalues = event_dict['jointfapvalues']
    idq_pipelines = config.get('idq_joint_fapCheck', 'idq_pipelines')
    idq_pipelines = idq_pipelines.replace(' ', '')
    idq_pipelines = idq_pipelines.split(',')
    for idqpipeline in idq_pipelines:
        pipeline_values = []
        for key in idqvalues.keys():
            if idqpipeline in key:
                pipeline_values.append(idqvalues[key])
        jointfapvalues[idqpipeline] = functools.reduce(operator.mul, pipeline_values, 1)

def idq_joint_fapCheck(event_dict, client, config, logger):
    group = event_dict['group']
    ignore_idq = config.get('idq_joint_fapCheck', 'ignore_idq')
    idq_joint_fapCheckresult = event_dict['idq_joint_fapCheckresult']
    if idq_joint_fapCheckresult!=None:
        return idq_joint_fapCheckresult
    elif group in ignore_idq:
        # logger.info('{0} -- {1} -- Not using idq checks for events with group(s) {2}.'.format(convertTime(), graceid, ignore_idq))
        event_dict['idq_joint_fapCheckresult'] = True
        return True
    else:
        pipeline = event_dict['pipeline']
        search = event_dict['search']
        idqthresh = get_idqthresh(pipeline, search, config)
        compute_joint_fap_values(event_dict, config)
        graceid = event_dict['graceid']
        idqvalues = event_dict['idqvalues']
        idqlogkey = event_dict['idqlogkey']
        instruments = event_dict['instruments']
        jointfapvalues = event_dict['jointfapvalues']
        idq_pipelines = config.get('idq_joint_fapCheck', 'idq_pipelines')
        idq_pipelines = idq_pipelines.replace(' ', '')
        idq_pipelines = idq_pipelines.split(',')
        if len(idqvalues)==0:
            message = '{0} -- {1} -- Have not gotten all the minfap values yet.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
            return None
        elif (0 < len(idqvalues) < (len(idq_pipelines)*len(instruments))):
            message = '{0} -- {1} -- Have not gotten all the minfap values yet.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
            if (min(idqvalues.values() and jointfapvalues.values()) < idqthresh):
                if idqlogkey=='no':
                    client.writeLog(graceid, 'AP: Finished running iDQ checks. Candidate event rejected because incomplete joint min-FAP value already less than iDQ threshold. {0} < {1}'.format(min(idqvalues.values() and jointfapvalues.values()), idqthresh), tagname='em_follow')
                    event_dict['idqlogkey']='yes'
                message = '{0} -- {1} -- iDQ check result: {2} < {3}'.format(convertTime(), graceid, min(idqvalues.values() and jointfapvalues.values()), idqthresh)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['idq_joint_fapCheckresult'] = False
                else:
                    pass
                #client.writeLabel(graceid, 'DQV') [apply DQV in parseAlert when return False]
                return False
        elif (len(idqvalues) > (len(idq_pipelines)*len(instruments))):
            message = '{0} -- {1} -- Too many minfap values in idqvalues dictionary.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
        else:
            message = '{0} -- {1} -- Ready to run iDQ checks.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
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
                message = '{0} -- {1} -- Got joint_fap = {2} for iDQ pipeline {3}.'.format(convertTime(), graceid, jointfap, idqpipeline)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                else:
                    pass
            if min(jointfapvalues.values()) > idqthresh:
                if idqlogkey=='no':
                    client.writeLog(graceid, 'AP: Finished running iDQ checks. Candidate event passed iDQ checks. {0} > {1}'.format(min(jointfapvalues.values()), idqthresh), tagname = 'em_follow')
                    event_dict['idqlogkey']='yes'
                message = '{0} -- {1} -- Passed iDQ check: {2} > {3}.'.format(convertTime(), graceid, min(jointfapvalues.values()), idqthresh)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['idq_joint_fapCheckresult'] = True
                else:
                    pass
                return True
            else:
                if idqlogkey=='no':
                    client.writeLog(graceid, 'AP: Finished running iDQ checks. Candidate event rejected due to low iDQ FAP value. {0} < {1}'.format(min(jointfapvalues.values()), idqthresh), tagname = 'em_follow')
                    event_dict['idqlogkey'] = 'yes'
                message = '{0} -- {1} -- iDQ check result: {2} < {3}'.format(convertTime(), graceid, min(jointfapvalues.values()), idqthresh)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                    event_dict['idq_joint_fapCheckresult'] = False
                else:
                    pass
                #client.writeLabel(graceid, 'DQV') [apply DQV in parseAlert when return False]
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

def operator_signoffCheck(event_dict, client, config, logger):
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
                    client.writeLog(graceid, 'AP: Candidate event failed operator signoff check.', tagname = 'em_follow')
                    event_dict['operatorlogkey'] = 'yes'
                    # client.writeLabel(graceid, 'DQV') [apply DQV in parseAlert when return False]
                event_dict['operator_signoffCheckresult'] = False
                return False
            else:
                message = '{0} -- {1} -- Not all operators have signed off yet.'.format(convertTime(), graceid)
                if loggerCheck(event_dict, message)==False:
                    logger.info(message)
                else:
                    pass
        else:
            if 'NO' in operatorsignoffs.values():
                if operatorlogkey=='no':
                    client.writeLog(graceid, 'AP: Candidate event failed operator signoff check.', tagname = 'em_follow')
                    event_dict['operatorlogkey'] = 'yes'
                    #client.writeLabel(graceid, 'DQV') [apply DQV in parseAlert when return False]
                event_dict['operator_signoffCheckresult'] = False
                return False
            else:
                if operatorlogkey=='no':
                    message = '{0} -- {1} -- Candidate event passed operator signoff check.'.format(convertTime(), graceid)
                    if loggerCheck(event_dict, message)==False:
                        logger.info(message)
                    else:
                        pass
                    client.writeLog(graceid, 'AP: Candidate event passed operator signoff check.', tagname = 'em_follow')
                    event_dict['operatorlogkey'] = 'yes'
                event_dict['operator_signoffCheckresult'] = True
                return True

#-----------------------------------------------------------------------
# advocate_signoffCheck
#-----------------------------------------------------------------------
def advocate_signoffCheck(event_dict, client, config, logger):
    advocate_signoffCheckresult = event_dict['advocate_signoffCheckresult']
    if advocate_signoffCheckresult!=None:
        return advocate_signoffCheckresult
    else:
        advocatelogkey = event_dict['advocatelogkey']
        advocatesignoffs = event_dict['advocatesignoffs']
        graceid = event_dict['graceid']
        if len(advocatesignoffs)==0:
            message = '{0} -- {1} -- Advocates have not signed off yet.'.format(convertTime(), graceid)
            if loggerCheck(event_dict, message)==False:
                logger.info(message)
            else:
                pass
        elif len(advocatesignoffs) > 0:
            if 'NO' in advocatesignoffs:
                if advocatelogkey=='no':
                    client.writeLog(graceid, 'AP: Candidate event failed advocate signoff check.', tagname = 'em_follow')
                    event_dict['advocatelogkey'] = 'yes'
                    #client.writeLabel(graceid, 'DQV') [apply DQV in parseAlert when return False]
                event_dict['advocate_signoffCheckresult'] = False
                return False
            else:
                if advocatelogkey=='no':
                    message = '{0} -- {1} -- Candidate event passed advocate signoff check.'.format(convertTime(), graceid)
                    if loggerCheck(event_dict, message)==False:
                        logger.info(message)
                    else:
                        pass
                    client.writeLog(graceid, 'AP: Candidate event passed advocate signoff check.', tagname = 'em_follow')
                    event_dict['advocatelogkey'] = 'yes'
                event_dict['advocate_signoffCheckresult'] = True
                return True
        
#-----------------------------------------------------------------------
# process_alert
#-----------------------------------------------------------------------
def process_alert(event_dict, voevent_type, client, config, logger):
    graceid = event_dict['graceid']
    pipeline = event_dict['pipeline']
    voeventerrors = event_dict['voeventerrors']
    voevents = event_dict['voevents']

    # check if we just sent this voevent
    if (len(voevents) > 0) and (voevent_type in sorted(voevents)[-1]):
        return
    else:
        pass

    # setting default internal value settings for alerts
    force_all_internal = config.get('general', 'force_all_internal')
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
            # check if we sent a retraction alert before
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
        else: # we have not sent voevents before, no need for retraction
            return

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
        injectionCheck(event_dict, client, config, logger)
        injection = event_dict['injectionsfound']
    else:
        injection = injectionsfound

    logger.info('{0} -- {1} -- Creating {2} VOEvent file locally.'.format(convertTime(), graceid, voevent_type))
    voevent = None
    thisvoevent = '{0}-(internal,injection):({1},{2})-'.format(len(voevents) + 1, internal, injection) + voevent_type

    try:
        r = client.createVOEvent(graceid, voevent_type, skymap_filename = skymap_filename, skymap_type = skymap_type, skymap_image_filename = skymap_image_filename, internal = internal)
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
            logger.info('{0} -- {1} -- {2}'.format(convertTime(), graceid, message))
            os.remove('/tmp/voevent_{0}_{1}.tmp'.format(graceid, number))
            return 'voevents, {0}'.format(thisvoevent)
        else:
            message = 'Error sending {0} VOEvent! {1}.'.format(voevent_type, error)
            client.writeLog(graceid, 'AP: Could not send VOEvent type {0}.'.format(voevent_type), tagname = 'em_follow')
            logger.info('{0} -- {1} -- {2}'.format(convertTime(), graceid, message))
            os.remove('/tmp/voevent_{0}_{1}.tmp'.format(graceid, number))
            listofvoeventerrors = ''
            for i in range(0, len(voeventerrors)):
                listofvoeventerrors += '{0} '.format(voeventerrors[i])
            if voevent_type in listofvoeventerrors:
                pass
            else:
                voeventerror_email = config.get('general', 'voeventerror_email')
                os.system('echo \'{0}\' | mail -s \'Problem sending {1} VOEvent: {2}\' {3}'.format(message, graceid, voevent_type, voeventerror_email))
            thisvoevent = '{0}-(internal,injection):({1},{2})-'.format(len(voeventerrors) + 1, internal, injection) + voevent_type
            voeventerrors.append(thisvoevent)
            return 'voeventerrors, {0}'.format(thisvoevent)

#-----------------------------------------------------------------------
# in the case we need to re-send alerts from outside the running
# approval_processorMP instance
#-----------------------------------------------------------------------
def resend_alert():
    # set up client
    config = ConfigParser.SafeConfigParser()
    config.read('{0}/childConfig-approval_processorMP.ini'.format(raw_input('childConfig-approval_processorMP.ini file directory? *do not include forward slash at end*\n')))
    client = config.get('general', 'client')
    print 'got client: {0}'.format(client)
    g = GraceDb('{0}'.format(client))

    # set up logger
    logger = logging.getLogger('approval_processorMP')
    logfile = config.get('general', 'approval_processorMP_logfile')
    homedir = os.path.expanduser('~')
    logging_filehandler = logging.FileHandler('{0}/public_html/monitor/approval_processorMP/files{1}'.format(homedir, logfile))
    logging_filehandler.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging_filehandler)

    # prompt for graceid
    graceid = str(raw_input('graceid:\n'))

    # prompt for voevent_type
    voevent_type = str(raw_input('voevent_type: (options are preliminary, initial, update, retraction)\n'))

    # load event dictionaries, get dictionary, send alert
    loadEventDicts()
    print eventDicts
    event_dict = eventDicts['{0}'.format(graceid)]
    response = process_alert(event_dict, voevent_type, g, config, logger)
    # to edit event_dict in parseAlert later
    response = re.findall(r'(.*), (.*)', response)

    # save event dictionaries
    saveEventDicts()
    sp.Popen('/usr/bin/gracedb log --tag-name=\'analyst_comments\' {0} \'resent VOEvent {1} in {2}\''.format(graceid, response[0][1], response[0][0]), stdout=sp.PIPE, shell=True)
    print 'saved event dicts'
    print 'voeventerrors: {0}'.format(event_dict['voeventerrors'])
    # prompt for exit
    exit_option = raw_input('exit: (options are yes or no)\n')
    if exit_option=='yes':
        exit()
    elif exit_option=='no':
        pass
