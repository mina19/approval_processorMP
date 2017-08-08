description = "utilities for approval_processorMP.py"
author = "Min-A Cho (mina19@umd.edu), Reed Essick (reed.essick@ligo.org), Deep Chatterjee (deep@uwm.edu)"

#-----------------------------------------------------------------------
# Import packages
#-----------------------------------------------------------------------

from queueItemsAndTasks import * ### DANGEROUS! but should be ok here...
from eventDictClassMethods import *
from approval_processorMPcommands import parseCommand

from lvalertMP.lvalert import lvalertMPutils as utils
from lal.gpstime import tconvert

import os
import json
import urllib
import logging
import time
import re

#-----------------------------------------------------------------------
# Activate a virtualenv in order to be able to use Comet.
#-----------------------------------------------------------------------

VIRTUALENV_ACTIVATOR = "/home/alexander.pace/emfollow_gracedb/cometenv/bin/activate_this.py" ### FIXME: this shouldn't be hard coded like this. 
                                                                                             ### If we need a virtual environment, it should be distributed along with the package.
                                                                                             ### That way, it is straightforward to install and run the code from *any* computer withour modifying the source code
execfile(VIRTUALENV_ACTIVATOR, dict(__file__=VIRTUALENV_ACTIVATOR))

#--------------------
# Definitions of which checks must be satisfied in each state before moving on
#--------------------

# main checks when currentstate of event is new_to_preliminary
selected_to_preliminary = [
    'ifosCheck',
    'farCheck',
    'labelCheck',
    'injectionCheck'
    ]

# main checks when currentstate of event is preliminary_to_initial
# will add human signoff and advocate checks later in parseAlert after reading config file
preliminary_to_initial = [
    'farCheck',
    'labelCheck',
    'have_lvem_skymapCheck',
    'idq_joint_fapCheck',
#    'virgo_dqCheck' XXX: removing virgo_dqCheck so that we do not get stalled for applying EM_READY label and sending out initial alerts
    ]

# tasks when currentstate of event is initial_to_update
initial_to_update = [
    'farCheck',
    'labelCheck',
    'have_lvem_skymapCheck'
    ]

#-----------------------------------------------------------------------
# parseAlert
#-----------------------------------------------------------------------
def parseAlert(queue, queueByGraceID, alert, t0, config):
    '''
    the way approval_processorMP digests lvalerts

    --> check if this alert is a command and delegate to parseCommand

    1) instantiates GraceDB client
    2) pulls childConfig settings
    3) makes sure we have the logger
    4) get lvalert specifics
    5) ensure we have the event_dict for the graceid = lvalert['uid']
    6) take proper action depending on the lvalert info coming in and currentstate of the event_dict 
    '''

    #-------------------------------------------------------------------
    # process commands sent via lvalert_commandMP
    #-------------------------------------------------------------------

    if alert['uid'] == 'command': ### this is a command message!
        return parseCommand( queue, queueByGraceID, alert, t0) ### delegate to parseCommand and return

    #-------------------------------------------------------------------
    # extract relevant config parameters and set up necessary data structures
    #-------------------------------------------------------------------

    # instantiate GraceDB client from the childConfig
    client = config.get('general', 'client')
    g = initGraceDb(client)

    # get other childConfig settings; save in configdict
    voeventerror_email        = config.get('general', 'voeventerror_email')
    force_all_internal        = config.get('general', 'force_all_internal')
    preliminary_internal      = config.get('general', 'preliminary_internal')
    forgetmenow_timeout       = config.getfloat('general', 'forgetmenow_timeout')
    approval_processorMPfiles = config.get('general', 'approval_processorMPfiles')
    hardware_inj              = config.get('labelCheck', 'hardware_inj')
    wait_for_hardware_inj     = config.getfloat('labelCheck', 'wait_for_hardware_inj')
    default_farthresh         = config.getfloat('farCheck', 'default_farthresh')
    time_duration             = config.getfloat('injectionCheck', 'time_duration')
    humanscimons              = config.get('operator_signoffCheck', 'humanscimons')

    ### extract options about advocates
    advocates      = config.get('advocate_signoffCheck', 'advocates')
    advocate_text  = config.get('advocate_signoffCheck', 'advocate_text')
    advocate_email = config.get('advocate_signoffCheck', 'advocate_email')

    ### extract options for GRB alerts
    em_coinc_text     = config.get('GRB_alerts', 'em_coinc_text')
    coinc_text        = config.get('GRB_alerts', 'coinc_text')
    grb_email         = config.get('GRB_alerts', 'grb_email')
    notification_text = config.get('GRB_alerts', 'notification_text')

    ### extract options about idq
    ignore_idq        = config.get('idq_joint_fapCheck', 'ignore_idq')
    default_idqthresh = config.getfloat('idq_joint_fapCheck', 'default_idqthresh')
    idq_pipelines     = config.get('idq_joint_fapCheck', 'idq_pipelines')
    idq_pipelines     = idq_pipelines.replace(' ','')
    idq_pipelines     = idq_pipelines.split(',')

    skymap_ignore_list = config.get('have_lvem_skymapCheck', 'skymap_ignore_list')

    ### set up configdict (passed to local data structure: eventDicts)
    configdict = makeConfigDict(config)

    # set up logging
    ### FIXME: why not open the logger each time parseAlert is called?
    ###        that would allow you to better control which loggers are necessary and minimize the number of open files.
    ###        it also minimizes the possibility of something accidentally being written to loggers because they were left open.
    ###        what's more, this is a natural place to set up multiple loggers, one for all data and one for data pertaining only to this graceid

    global logger
    if globals().has_key('logger'): # check to see if we have logger
        logger = globals()['logger']
    else: # if not, set one up
        logger = loadLogger(config)
        logger.info('\n{0} ************ approval_processorMP.log RESTARTED ************\n'.format(convertTime()))

    global gpstime_of_restart
    if globals().has_key('gpstime_of_restart'): # check to see if this is the first lvalert we process after a restart of approval processor
        gpstime_of_restart = globals()['gpstime_of_restart']
    else: # this is needed later for grouper, so that upon a restart of approval_processor, we know whether we need to query gracedb or not
        utc_t0 = convertTime(t0) # t0 is in linux time. we converted it into a UTC string
        gpstime_of_restart = float(tconvert(utc_t0))

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

    if alert_type=='new': ### new event -> we must first create event_dict and set up ForgetMeNow queue item for G events

        ### create event_dict
        event_dict = EventDict() # create a new instance of EventDict class which is a blank event_dict
        if is_external_trigger(alert)==True: # this is an external GRB trigger
            event_dict.grb_trigger_setup(alert['object'], graceid, g, config, logger) # populate this event_dict with grb trigger info from lvalert
        else:
            event_dict.setup(alert['object'], graceid, configdict, g, config, logger) # populate this event_dict with information from lvalert
        eventDicts[graceid] = event_dict # add the instance to the global eventDicts
        eventDictionaries[graceid] = event_dict.data # add the dictionary to the global eventDictionaries

        ### ForgetMeNow queue item
        item = ForgetMeNow( t0, forgetmenow_timeout, graceid, eventDicts, queue, queueByGraceID, logger)
        queue.insert(item) # add queue item to the overall queue

        ### set up queueByGraceID
        newSortedQueue = utils.SortedQueue() # create sorted queue for event candidate
        newSortedQueue.insert(item) # put ForgetMeNow queue item into the sorted queue
        queueByGraceID[item.graceid] = newSortedQueue # add queue item to the queueByGraceID
        saveEventDicts(approval_processorMPfiles) # trying to see if expirationtime is updated from None

        message = '{0} -- {1} -- Created event dictionary for {1}.'.format(convertTime(), graceid)
        if loggerCheck(event_dict.data, message)==False:
            logger.info(message)
            g.writeLog(graceid, 'AP: Created event dictionary.', tagname='em_follow')
        else:
            pass

    else: ### not a new alert -> we may already be tracking this graceid

        if eventDicts.has_key(graceid): ### we're already tracking it

            # get event_dict with expirationtime key updated for the rest of parseAlert
            event_dict = eventDicts[graceid]

            # find ForgetMeNow corresponding to this graceid and update expiration time
            for item in queueByGraceID[graceid]:
                if item.name==ForgetMeNow.name: # selects the queue item that is a ForgetMeNow instance
                    item.setExpiration(t0) # updates the expirationtime key
                    queue.resort() ### may be expensive, but is needed to guarantee that queue remains sorted
                    queueByGraceID[graceid].resort()
                    break
            else: ### we couldn't find a ForgetMeNow for this event! Something is wrong!
                os.system('echo \'ForgetMeNow KeyError\' | mail -s \'ForgetMeNow KeyError {0}\' {1}'.format(graceid, advocate_email))       
                raise KeyError('could not find ForgetMeNow for %s'%graceid) ### Reed thinks this is necessary as a safety net. 
                                                                            ### we want the process to terminate if things are not set up correctly to force us to fix it

        else: # event_dict for event candidate does not exist. we need to create it with up-to-date information
            event_dict = EventDict() # create a new instance of the EventDict class which is a blank event_dict
            if is_external_trigger(alert)==True:
                event_dict.grb_trigger_setup(g.events(graceid).next(), graceid, g, config, logger)
            else:
                event_dict.setup(g.events(graceid).next(), graceid, configdict, g, config, logger) # fill in event_dict using queried event candidate dictionary
                event_dict.update() # update the event_dict with signoffs and iDQ info
            eventDicts[graceid] = event_dict # add this instance to the global eventDicts
            eventDictionaries[graceid] = event_dict.data # add the dictionary to the global eventDictionaries

            # create ForgetMeNow queue item and add to overall queue and queueByGraceID
            item = ForgetMeNow(t0, forgetmenow_timeout, graceid, eventDicts, queue, queueByGraceID, logger)
            queue.insert(item) # add queue item to the overall queue

            ### set up queueByGraceID
            newSortedQueue = utils.SortedQueue() # create sorted queue for new event candidate
            newSortedQueue.insert(item) # put ForgetMeNow queue item into the sorted queue
            queueByGraceID[item.graceid] = newSortedQueue # add queue item to the queueByGraceID

            message = '{0} -- {1} -- Created event dictionary for {1}.'.format(convertTime(), graceid)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Created event dictionary.', tagname='em_follow')
            else:
                pass

    #--------------------
    # ignore alerts that are not relevant, like simulation or MDC events
    #--------------------

    # if the graceid starts with 'M' for MDCs or 'S' for Simulation, ignore
    if re.match('M', graceid) or re.match('S', graceid): ### FIXME: we want to make this a config-file option!
        message = '{0} -- {1} -- Mock data challenge or simulation. Ignoring.'.format(convertTime(), graceid)
        if loggerCheck(event_dict.data, message)==False:
            logger.info(message)
            g.writeLog(graceid, 'AP: Mock data challenge or simulation. Ignoring.', tagname='em_follow')
        else:
            pass
        saveEventDicts(approval_processorMPfiles)
        return 0

    #--------------------
    # take care of external GRB triggers
    #--------------------
    if is_external_trigger(alert)==True: # for now, grouped everything related to external triggers together below
        # if it's not a log message updating us about possible coincidence with gravitational-waves OR labels OR json file uploads we are not interested
        if alert_type=='label':
            record_label(event_dict.data, description)
        if alert_type=='update':
            # is this a comment containing coinc info that needs to be parsed?
            if 'comment' in alert['object'].keys():
                comment = alert['object']['comment']
                if 'Significant event in on-source' in comment: # got comment structure from Dipongkar
                    coinc_pipeline, coinc_fap = record_coinc_info(event_dict.data, comment, alert, logger)
                    # begin creating the dictionary that will turn into json file
                    message_dict = {}
                    # populate text field for the GCN circular-to-be
                    message_dict['message'] = coinc_text.format(graceid, coinc_fap)
                    message_dict['loaded_to_gracedb'] = 0
                    # make json string and file
                    message_dict = json.dumps(message_dict)
                    tmpfile = open('/tmp/coinc_{0}.json'.format(graceid), 'w')
                    tmpfile.write(message_dict)
                    tmpfile.close()
                    # make sure to load with a comment that we look for to check off that it's been loaded into gracedb
                    # was it an online or offline pipeline?
                    if 'Online' in coinc_pipeline:
                        event_dict.data['grb_online_json'] = message_dict
                        g.writeLog(graceid, 'GRB-GW Coincidence JSON file: grb_online_json', '/tmp/coinc_{0}.json'.format(graceid), tagname = 'em_follow')
                    elif 'Offline' in coinc_pipeline:
                        event_dict.data['grb_offline_json'] = message_dict
                        g.writeLog(graceid, 'GRB-GW Coincidence JSON file: grb_offline_json', '/tmp/coinc_{0}.json'.format(graceid), tagname = 'em_follow')
                    os.remove('/tmp/coinc_{0}.json'.format(graceid))
                    ### alert via email
                    os.system('mail -s "Coincidence JSON created for {0}" {1} <<< "{2}"'.format(graceid, grb_email, notification_text))
                # is this the json file loaded into GraceDb?
                if 'GRB-GW Coincidence JSON file' in comment:
                    # if it is, find out which type of json it was and then message_dict['loaded_to_gracedb'] = 1
                    json_type = re.findall('file: (.*)', comment)[0]
                    message_dict = event_dict.data[json_type]
                    message_dict = json.loads(message_dict) # converts string to dictionary
                    message_dict['loaded_to_gracedb'] = 1
                    # when we send to observers, message_dict['sent_to_observers'] = 1
            else:
                pass
        saveEventDicts(approval_processorMPfiles)
        return 0

    #--------------------
    # Appending which checks must be satisfied in preliminary_to_initial state before moving on
    #--------------------

    if humanscimons=='yes':
        preliminary_to_initial.append('operator_signoffCheck')
    if advocates=='yes':
        preliminary_to_initial.append('advocate_signoffCheck')

    #--------------------
    # update information based on the alert_type
    # includes extracting information from the alert
    # may also include generating VOEvents and issuing them
    #--------------------

    # actions for each alert_type
    currentstate = event_dict.data['currentstate'] ### actions depend on the current state
       
    ### NOTE: we handle alert_type=="new" above as well and this conditional is slightly redundant...
    if alert_type=='new':

        #----------------
        ### pass event through PipelineThrottle
        #----------------

        ### check if a PipelineThrottle exists for this node
        group    = event_dict.data['group']
        pipeline = event_dict.data['pipeline']
        search   = event_dict.data['search']
        key = generate_ThrottleKey(group, pipeline, search=search)
        if queueByGraceID.has_key(key): ### a throttle already exists
            if len(queueByGraceID[key]) > 1:
                raise ValueError('too many QueueItems in SortedQueue for pipelineThrottle key=%s'%key)
            item = queueByGraceID[key][0] ### we expect there to be only one item in this SortedQueue

        else: ### we need to make a throttle!
            # pull PipelineThrottle parameters from the config
            if config.has_section(key):
                throttleWin          = config.getfloat(key, 'throttleWin')
                targetRate           = config.getfloat(key, 'targetRate')
                requireManualReset   = config.getboolean(key, 'requireManualReset')
                conf                 = config.getfloat(key, 'conf')

            else:
                throttleWin          = config.getfloat('default_PipelineThrottle', 'throttleWin')
                targetRate           = config.getfloat('default_PipelineThrottle', 'targetRate')
                requireManualReset   = config.getboolean('default_PipelineThrottle', 'requireManualReset')
                conf                 = config.getfloat('default_PipelineThrottle', 'conf')
            grouperWin = config.getfloat('grouper', 'grouperWin')
            item = PipelineThrottle(t0, eventDictionaries, grouperWin, throttleWin, targetRate, group, pipeline, search=search, requireManualReset=requireManualReset, conf=conf, graceDB_url=client)

            queue.insert( item ) ### add to overall queue

            newSortedQueue = utils.SortedQueue() # create sorted queue for event candidate
            newSortedQueue.insert(item) # put PipelineThrottle queue item into the sorted queue
            queueByGraceID[item.graceid] = newSortedQueue # add queue item to the queueByGraceID

        item.addEvent( graceid, t0 ) ### add new event to throttle
                                       ### this takes care of labeling in gracedb as necessary

        if item.isThrottled(): 
            ### send some warning message?
            return 0 ### we're done here because we're ignoring this event -> exit from parseAlert

        #----------------
        ### pass data to Grouper
        #----------------
        ### due to the time sensitivity of grouper, first check to see if an existing grouper exists
        ### get the best groupTag from the queueByGraceID for this event gpstime, or create a new groupTag
        grouperWin = config.getfloat('grouper', 'grouperWin')
        groupTag = generate_GroupTag(graceid, grouperWin, queueByGraceID, eventDictionaries)

        ### check to see if Grouper exists for this groupTag
        if queueByGraceID.has_key(groupTag): ### this is not a new Grouper we have to create, so pull it up
            if len(queueByGraceID[groupTag]) > 1:
                raise ValueError('too many QueueItems in SortedQueue for groupTag={0}'.format(groupTag))
            item = queueByGraceID[groupTag][0] ### there should only be one item in this SortedQueue
            item.addEvent( graceid ) ### add this graceid to the item

        else: ### have we already made a decision about triggers with gpstimes close to this event's gpstime?
            already_selected = False
            query_string = '{0} .. {1}'.format(str(event_dict.data['gpstime']-grouperWin), str(event_dict.data['gpstime']+grouperWin))
            events = g.events(query_string) # query GraceDb for events
            for event in events: # look to see if any were labeled EM_Selected
                labels = event['labels'] # get the dictionary of labels
                if labels.has_key('EM_Selected'):
                   already_selected = True
            if already_selected: # label this event as EM_Superseded, no need to do more
                g.writeLabel(graceid, 'EM_Superseded')
                return 0
            else: # we need to make a groupTag and grouper, or pull down existing ones
                pass

            decisionWin = config.getfloat('grouper', 'decisionWin')
            item = Grouper(t0, grouperWin, groupTag, eventDictionaries, decisionWin, graceDB_url=client) ### create the actual QueueItem

            queue.insert( item ) ### insert it in the overall queue

            newSortedQueue = utils.SortedQueue() ### set up the SortedQueue for queueByGraceID
            newSortedQueue.insert(item)
            queueByGraceID[groupTag] = newSortedQueue
            item.addEvent( graceid ) ### add this graceid to the item

        ### update the event dictionaries for all members of this group to reflect all the current members of the group with this groupTag
        for groupMember in item.events:
            eventDictionaries[groupMember]['grouperGroupMembers'] = item.events

        saveEventDicts(approval_processorMPfiles)
        return 0 ### we're done here. When Grouper makes a decision, we'll tick through the rest of the processes with a "EM_Selected" label

    elif alert_type=='label':
        record_label(event_dict.data, description)

        if description=='PE_READY': ### PE_READY label was just applied. We may need to send an update alert

            message = '{0} -- {1} -- Sending update VOEvent.'.format(convertTime(), graceid)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Received PE_READY label. Sending update VOEvent.', tagname='em_follow')
                process_alert(event_dict.data, 'update', g, config, logger)

            else:
                pass

            message = '{0} -- {1} -- State: {2} --> complete.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: State: {0} --> complete.'.format(currentstate), tagname='em_follow')
                event_dict.data['currentstate'] = 'complete'

            else:
                pass

        elif description=='EM_READY': ### EM_READY label was just applied. We may need to send an initial alert
            message = '{0} -- {1} -- Sending initial VOEvent.'.format(convertTime(), graceid)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Received EM_READY label. Sending initial VOEvent.', tagname='em_follow')
                process_alert(event_dict.data, 'initial', g, config, logger)

            else:
                pass

            message = '{0} -- {1} -- State: {2} --> initial_to_update.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: State: {0} --> initial_to_update.'.format(currentstate), tagname='em_follow')
                event_dict.data['currentstate'] = 'initial_to_update'

            else:
                pass

        elif description=="EM_Throttled": ### the event is throttled and we need to turn off all processing for it

            event_dict.data['currentstate'] = 'throttled' ### update current state
            
            ### check if we need to send retractions
            voevents = event_dict.data['voevents']
            if len(voevents) > 0:
                if 'retraction' not in sorted(voevents)[-1]:
                    # there are existing VOEvents we've sent, but no retraction alert
                    process_alert(event_dict.data, 'retraction', g, config, logger)

            ### update ForgetMeNow expiration to handle all the clean-up?
            ### we probably do NOT want to change the clean-up schedule because we'll still likely receive a lot of alerts about this guy
            ### therefore, we just retain the local data and ignore him, rather than erasing the local data and having to query to reconstruct it repeatedly as new alerts come in
#            for item in queueByGraceID[graceid]: ### update expiration of the ForgetMeNow so it is immediately processed next.
#                if item.name == ForgetMeNow.name:
#                    time.setExpiration(-np.infty )
#                                                                ### FIXME: this can break the order in SortedQueue's. We need to pop and reinsert or call a manual resort
#                    queue.resort() ### may be expensive but is needed to guarantee that queue remains sorted
#                    queueByGraceID[graceid].resort()
#                    break
#            else:
#                raise ValueError('could not find ForgetMeNow QueueItem for graceid=%s'%graceid)

        elif description=="EM_Superseded": ### this event was superceded by another event within Grouper
            # the currentstate should be updated to em_superseded
            event_dict.data['currentstate'] = 'superseded' 

        elif (checkLabels(description.split(), config) > 0): ### some other label was applied. We may need to issue a retraction notice.
            event_dict.data['currentstate'] = 'rejected'

            ### check to see if we need to send a retraction
            voevents = event_dict.data['voevents']
            if len(voevents) > 0:
                if 'retraction' not in sorted(voevents[-1]):
                    # there are existing VOEvents we've sent, but no retraction alert
                    process_alert(event_dict.data, 'retraction', g, config, logger)

        saveEventDicts(approval_processorMPfiles) ### save the updated eventDict to disk
        if description=='EM_Selected':
            event_dict.data['currentstate'] = 'selected_to_preliminary'
            # we want to get to the block of code where we perform checks for selected_to_preliminary events so pass, rather than return 0
            pass
        else:
            return 0

    elif alert_type=='update':
        # first the case that we have a new lvem skymap
        if (filename.endswith('.fits.gz') or filename.endswith('.fits')):
            if 'lvem' in alert['object']['tag_names']: # we only care about skymaps tagged lvem for sharing with MOU partners
                submitter = alert['object']['issuer']['display_name'] # in the past, we used to care who submitted skymaps; keeping this functionality just in case
                record_skymap(event_dict.data, filename, submitter, logger)
            else:
                pass
        # interested in iDQ information or other updates
        else:
            if 'comment' in alert['object'].keys():
                comment = alert['object']['comment']
                if re.match('minimum glitch-FAP', comment): # looking to see if it's iDQ glitch-FAP information
                    record_idqvalues(event_dict.data, comment, logger)
                elif re.match('resent VOEvent', comment): # looking to see if another running instance of approval_processorMP sent a VOEvent
                    response = re.findall(r'resent VOEvent (.*) in (.*)', comment) # extracting which VOEvent was re-sent
                    event_dict.data[response[0][1]].append(response[0][0])
                    saveEventDicts(approval_processorMPfiles)
                elif 'EM-Bright probabilities computed from detection pipeline' in comment: # got comment structure from Shaon G.
                    record_em_bright(event_dict.data, comment, logger)
                elif 'Temporal coincidence with external trigger' in comment: # got comment structure from Alex U.
                    exttrig, coinc_far = record_coinc_info(event_dict.data, comment, alert, logger)
                    # create dictionary that will become json file
                    message_dict = {}
                    grb_instrument = eventDictionaries[exttrig]['pipeline']
                    message_dict['message'] = em_coinc_text.format(exttrig, grb_instrument, graceid, coinc_far)
                    message_dict['loaded_to_gracedb'] = 0
                    message_dict = json.dumps(message_dict)
                    # update event dictionaries for both the gw and external trigger
                    eventDictionaries[exttrig]['em_coinc_json'] = message_dict # this updates the external trigger event_dict.data
                    event_dict.data['em_coinc_json'] = message_dict # this updates the gw trigger event_dict.data
                    # load json file to the gw gracedb page
                    tmpfile = open('/tmp/coinc_{0}.json'.format(graceid), 'w')
                    tmpfile.write(message_dict)
                    tmpfile.close()
                    g.writeLog(graceid, 'GRB-GW Coincidence JSON file: em_coinc_json', '/tmp/coinc_{0}.json'.format(graceid), tagname = 'em_follow')
                    os.remove('/tmp/coinc_{0}.json'.format(graceid))
                    # load json file to the external trigger page
                    tmpfile = open('/tmp/coinc_{0}.json'.format(exttrig), 'w')
                    tmpfile.write(message_dict)
                    tmpfile.close()
                    g.writeLog(exttrig, 'GRB-GW Coincidence JSON file: em_coinc_json', '/tmp/coinc_{0}.json'.format(exttrig), tagname = 'em_follow')
                    os.remove('/tmp/coinc_{0}.json'.format(exttrig))
                    ### alert via email
                    os.system('mail -s "Coincidence JSON created for {0}" {1} <<< "{2}"'.format(exttrig, grb_email, notification_text))
                    saveEventDicts(approval_processorMPfiles)
                elif 'GRB-GW Coincidence JSON file' in comment: # this is the comment that accompanies a loaded coinc json file
                    message_dict = event_dict.data['em_coinc_json']
                    message_dict = json.loads(message_dict) # converts string to dictionary
                    message_dict['loaded_to_gracedb'] = 1
                    saveEventDicts(approval_processorMPfiles)
                #elif 'V1 veto channel' in comment and comment.endswith('vetoed'): # this is a Virgo Veto statement we need to record
                #    record_virgo_dqIsVetoed(event_dict.data, comment, logger)
                #elif 'V1 hardware injection' in comment and comment.endswith('injections'): # this is a Virgo hardware injection statement we need to record
                #    record_virgoInjections(event_dict.data, comment, logger)
                else:
                    pass

    elif alert_type=='signoff':
        signoff_object = alert['object']
        record_signoff(event_dict.data, signoff_object)

    #---------------------------------------------
    # run checks specific to currentstate of the event candidate
    #---------------------------------------------

    passedcheckcount = 0

    if currentstate=='selected_to_preliminary':
        for Check in selected_to_preliminary:
            eval('event_dict.{0}()'.format(Check))
            checkresult = event_dict.data[Check + 'result']
            if checkresult==None:
                pass
            elif checkresult==False:
                # because in 'selected_to_preliminary' state, no need to apply DQV label
                message = '{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: Failed {0} in currentstate: {1}.'.format(Check, currentstate), tagname='em_follow')
                else:
                    pass
                message = '{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: State: {0} --> rejected.'.format(currentstate), tagname='em_follow')
                    event_dict.data['currentstate'] = 'rejected'
                else:
                    pass
                saveEventDicts(approval_processorMPfiles)
                return 0
            elif checkresult==True:
                passedcheckcount += 1
        if passedcheckcount==len(selected_to_preliminary):
            message = '{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Passed all {0} checks.'.format(currentstate), tagname='em_follow')
            else:
                pass
            message = '{0} -- {1} -- Sending preliminary VOEvent.'.format(convertTime(), graceid)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Sending preliminary VOEvent.', tagname='em_follow')
                process_alert(event_dict.data, 'preliminary', g, config, logger)
            else:
                pass
            message = '{0} -- {1} -- State: {2} --> preliminary_to_initial.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: State: {0} --> preliminary_to_initial.'.format(currentstate), tagname='em_follow')
                event_dict.data['currentstate'] = 'preliminary_to_initial'
            else:
                pass
            labels = event_dict.data['labels']
            # notify the operators if we haven't previously processed this event
            instruments = event_dict.data['instruments']
            for instrument in instruments:
                if instrument in str(labels):
                    pass
                else:
                    message = '{0} -- {1} -- Labeling {2}OPS.'.format(convertTime(), graceid, instrument)
                    if loggerCheck(event_dict.data, message)==False:
                        logger.info(message)
                        g.writeLog(graceid, 'AP: Labeling {0}OPS.'.format(instrument), tagname='em_follow')
                        g.writeLabel(graceid, '{0}OPS'.format(instrument))
                    else:
                        pass
            # notify the advocates if we haven't previously processed this event
            if 'ADV' in str(labels):
                pass
            else:
                message = '{0} -- {1} -- Labeling ADVREQ.'.format(convertTime(), graceid)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: Labeling ADVREQ.', tagname='em_follow')
                    g.writeLabel(graceid, 'ADVREQ')
                    os.system('echo \'{0}\' | mail -s \'{1} passed criteria for follow-up\' {2}'.format(advocate_text, graceid, advocate_email))
                    # expose event to LV-EM
                    url_perm_base = g.service_url + urllib.quote('events/{0}/perms/gw-astronomy:LV-EM:Observers/'.format(graceid))
                    for perm in ['view', 'change']:
                        url = url_perm_base + perm
                        #g.put(url)
                else:
                    pass
        saveEventDicts(approval_processorMPfiles)
        return 0

    elif currentstate=='preliminary_to_initial':
        for Check in preliminary_to_initial:
            eval('event_dict.{0}()'.format(Check))
            checkresult = event_dict.data[Check + 'result']
            if checkresult==None:
                pass
            elif checkresult==False:
                message = '{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: Failed {0} in currentstate: {1}.'.format(Check, currentstate), tagname='em_follow')
                else:
                    pass
                message = '{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: State: {0} --> rejected.'.format(currentstate), tagname='em_follow')
                    event_dict.data['currentstate'] = 'rejected'
                else:
                    pass
                # need to set DQV label so long as it isn't the operator_signoffCheck or advocate_signoffCheck
                if 'signoffCheck' in Check:
                    message = '{0} -- {1} -- Not labeling DQV because signoffCheck is separate from explicit data quality checks.'.format(convertTime(), graceid)
                    if loggerCheck(event_dict.data, message)==False:
                        logger.info(message)
                        g.writeLog(graceid, 'AP: Not labeling DQV because signoffCheck is separate from explicit data quality checks.', tagname='em_follow')
                    else:
                        pass
                else:
                    message = '{0} -- {1} -- Labeling DQV.'.format(convertTime(), graceid)
                    if loggerCheck(event_dict.data, message)==False:
                        logger.info(message)
                        g.writeLog(graceid, 'AP: Labeling DQV.', tagname='em_follow')
                        g.writeLabel(graceid, 'DQV')
                    else:
                        pass
                saveEventDicts(approval_processorMPfiles)
                return 0
            elif checkresult==True:
                passedcheckcount += 1
                if Check=='have_lvem_skymapCheck': # we want to send skymaps out as quickly as possible, even if humans have not vetted the event
                    process_alert(event_dict.data, 'preliminary', g, config, logger) # if it turns out we've sent this alert with this skymap before, the process_alert function will just not send this repeat
        if passedcheckcount==len(preliminary_to_initial):
            message = '{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Passed all {0} checks.'.format(currentstate), tagname='em_follow')
            else:
                pass
            message = '{0} -- {1} -- Labeling EM_READY.'.format(convertTime(), graceid)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Labeling EM_READY.', tagname='em_follow')
                g.writeLabel(graceid, 'EM_READY')
            else:
                pass
        saveEventDicts(approval_processorMPfiles)
        return 0

    elif currentstate=='initial_to_update':
        for Check in initial_to_update:
            eval('event_dict.{0}()'.format(Check))
            checkresult = event_dict.data[Check + 'result']
            if checkresult==None:
                pass
            elif checkresult==False:
               # need to set DQV label
                message = '{0} -- {1} -- Failed {2} in currentstate: {3}.'.format(convertTime(), graceid, Check, currentstate)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: Failed {0} in currentstate: {1}.'.format(Check, currentstate), tagname='em_follow')
                else:
                    pass
                message = '{0} -- {1} -- State: {2} --> rejected.'.format(convertTime(), graceid, currentstate)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: State: {0} --> rejected.'.format(currentstate), tagname='em_follow')
                    event_dict.data['currentstate'] = 'rejected'
                else:
                    pass
                message = '{0} -- {1} -- Labeling DQV.'.format(convertTime(), graceid)
                if loggerCheck(event_dict.data, message)==False:
                    logger.info(message)
                    g.writeLog(graceid, 'AP: Labeling DQV.', tagname='em_follow')
                    g.writeLabel(graceid, 'DQV')
                else:
                    pass
                saveEventDicts(approval_processorMPfiles)
                return 0
            elif checkresult==True:
                passedcheckcount += 1
        if passedcheckcount==len(initial_to_update):
            message = '{0} -- {1} -- Passed all {2} checks.'.format(convertTime(), graceid, currentstate)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Passed all {0} checks.'.format(currentstate), tagname='em_follow')
            else:
                pass
            message = '{0} -- {1} -- Labeling PE_READY.'.format(convertTime(), graceid)
            if loggerCheck(event_dict.data, message)==False:
                logger.info(message)
                g.writeLog(graceid, 'AP: Labeling PE_READY.', tagname='em_follow')
                g.writeLabel(graceid, 'PE_READY')
            else:
                pass
        saveEventDicts(approval_processorMPfiles)
        return 0
    
    else:
        saveEventDicts(approval_processorMPfiles)
        return 0
