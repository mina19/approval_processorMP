description = "methods and attributes of the EventDict class"
author = "Min-A Cho (mina19@umd.edu)"

#-----------------------------------------------------------------------
# Import packages
#-----------------------------------------------------------------------
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
# Creating the global event dictionaries variable for local bookkeeping
#-----------------------------------------------------------------------
global eventDicts # global variable for local bookkeeping of event candidate checks, files, labels, etc. 
### important thing is it saves the event_dict as an INSTANCE of the EventDict class
eventDicts = {} # it's a dictionary storing data in the form 'graceid': event_dict where each event_dict is created below in class EventDict

global eventDictionaries # global variable for local bookkeeping
### important thing is it saves the event_dict as a DICTIONARY
eventDictionaries = {}
#-----------------------------------------------------------------------
# Define initGracedb() function
#-----------------------------------------------------------------------
def initGraceDb(client):
    if 'http' in client:
        g = GraceDb(client)
    else:
        # assume local path to FAKE_DB is passed
        from ligoTest.gracedb.rest import FakeDb
        # FakeDb directory is created if non-existent
        if os.path.exists(client):
            g = FakeDb(client)
        else:
            g = None
    return g
#-----------------------------------------------------------------------

#-----------------------------------------------------------------------
# EventDict class
#-----------------------------------------------------------------------
class EventDict():
    '''
    creates an event_dict for each event candidate to keep track of checks, files, comments, labels coming in
    '''
    def __init__(self):
        self.data = {} # create a blank dictionary that gets populated later

    def __getitem__(self, key):
        self.key = key
        return self.data[self.key]

    def setup(self, dictionary, graceid, configdict, client, config, logger):
        self.dictionary = dictionary # a dictionary either extracted from an lvalert or from a call to graceDb
        self.graceid = graceid
        self.configdict = configdict # stores settings used
        self.client = client
        self.config = config
        self.logger = logger
        self.data.update({
            'advocate_signoffCheckresult': None,
            'advocatelogkey'             : 'no',
            'advocatesignoffs'           : [],
            'configuration'              : self.configdict,
            'currentstate'               : 'new_to_preliminary',
            'far'                        : self.dictionary['far'],
            'farCheckresult'             : None,
            'farlogkey'                  : 'no',
            'em_coinc_json'              : None,
            'expirationtime'             : None,
            'external_trigger'           : None,
            'gpstime'                    : float(self.dictionary['gpstime']),
            'graceid'                    : self.graceid,
            'group'                      : self.dictionary['group'],
            'groupergroup'               : {},
            'have_lvem_skymapCheckresult': None,
            'idq_joint_fapCheckresult'   : None,
            'idqlogkey'                  : 'no',
            'idqvalues'                  : {},
            'ifoslogkey'                 : 'no',
            'ifosCheckresult'            : None,
            'injectionCheckresult'       : None,
            'injectionsfound'            : None,
            'injectionlogkey'            : 'no',
            'instruments'                : str(self.dictionary['instruments']).split(','),
            'jointfapvalues'             : {},
            'labelCheckresult'           : None,
            'labels'                     : self.dictionary['labels'].keys(),
            'lastsentskymap'             : None,
            'lastsentpreliminaryskymap'  : None,
            'loggermessages'             : [],
            'lvemskymaps'                : {},
            'operator_signoffCheckresult': None,
            'operatorlogkey'             : 'no',
            'operatorsignoffs'           : {},
            'pipeline'                   : self.dictionary['pipeline'],
            'search'                     : self.dictionary['search'] if self.dictionary.has_key('search') else '',
            'voeventerrors'              : [],
            'voevents'                   : []
        })

    def update(self):
        '''
        creates an event_dict with signoff and iDQ information for self.graceid
        this event_dict starts off with currentstate new_to_preliminary
        '''
        # get the most recent voevent information
        voevent_dicts = self.client.voevents(self.graceid).json()['voevents']
        for voevent in voevent_dicts: # this traverses voevents in the order they were sent
            voevent_text = voevent['text'] # this is the actual xml text
            internal     = re.findall(r'internal\" dataType=\"int\" value=\"(\S+)\"', voevent_text)[0]
            vetted       = re.findall(r'Vetted\" dataType=\"int\" value=\"(\S+)\"', voevent_text)[0] 
            open_alert   = re.findall(r'OpenAlert\" dataType=\"int\" value=\"(\S+)\"', voevent_text)[0] 
            hardware_inj = re.findall(r'HardwareInj\" dataType=\"int\" value=\"(\S+)\"', voevent_text)[0]
            voevent_type = voevent['voevent_type']
            if voevent_type=='PR':
                voevent_type = 'preliminary'
            elif voevent_type=='IN':
                voevent_type = 'initial'
            elif voevent_type=='UP':
                voevent_type = 'update'
            elif voevent_type=='RE':
                voevent_type = 'retraction'
            # update sent skymaps if any from the voevent
            skymap = re.findall(r'skymap_fits_basic\" dataType=\"string\" value=\"(\S+)\"', voevent_text)
            # update event_dict in the case there were any skymaps
            if len(skymap)==1:
                skymap = re.findall(r'files/(\S+)', skymap[0])[0]
                if voevent_type=='preliminary':
                    self.data['lastsentpreliminaryskymap'] = skymap
                elif voevent_type=='initial' or voevent_type=='update':
                    self.data['lastsentskymap'] = skymap
            elif len(skymap)==0:
                skymap = None
            thisvoevent = '(internal,vetted,open_alert,hardware_inj,skymap):({0},{1},{2},{3},{4})-'.format(internal, vetted, open_alert, hardware_inj, skymap) + voevent_type
            thisvoevent = '{0}-'.format(len(self.data['voevents']) + 1) + thisvoevent
            self.data['voevents'].append(thisvoevent)


        # update signoff information if available
        url = self.client.templates['signoff-list-template'].format(graceid=self.graceid) # construct url for the operator/advocate signoff list
        signoff_list = self.client.get(url).json()['signoff'] # pull down signoff list
        for signoff_object in signoff_list:
            record_signoff(self.data, signoff_object)

        # update iDQ information, skymaps, EM-Bright information, and past farCheck results if available
        log_dicts = self.client.logs(self.graceid).json()['log']
        for message in log_dicts: # going through the log from oldest to most recent for recording skymaps
            if 'lvem' in message['tag_names'] and '.fits' in message['filename']:
                record_skymap(self.data, message['filename'], message['issuer']['display_name'], logger) # this way, the ordering in which the skymaps came in is properly noted
            else:
                pass

        for message in reversed(log_dicts): # going through the log from most recent to oldest message
            if re.match('minimum glitch-FAP', message['comment']):
                record_idqvalues(self.data, message['comment'], logger)
            elif re.match('EM-Bright probabilities computed from detection pipeline', message['comment']):
                record_em_bright(self.data, message['comment'], logger)
            elif re.match('AP: Candidate event rejected due to large FAR', message['comment']):
                default_farthresh = float(re.findall(r'>= (.*)', message['comment'])[0])
                self.configdict['default_farthresh'] = default_farthresh
                self.data['configuration'] = self.configdict
                self.data['farlogkey'] = 'yes'
                self.data['farCheckresult'] = False
            elif re.match('AP: Candidate event has low enough FAR', message['comment']):
                default_farthresh = float(re.findall(r'< (.*)', message['comment'])[0])
                self.configdict['default_farthresh'] = default_farthresh
                self.data['configuration'] = self.configdict
                self.data['farlogkey'] = 'yes'
                self.data['farCheckresult'] = True
            else:
                pass               

    #-----------------------------------------------------------------------
    # external GRB trigger local data bookkeeping
    #-----------------------------------------------------------------------
    def grb_trigger_setup(self, dictionary, graceid, client, config, logger):
        self.dictionary = dictionary # a dictionary either extracted from an lvalert or from a call to gracedb
        self.graceid = graceid
        self.client = client
        self.config = config
        self.logger = logger
        self.data.update({
            'em_coinc_json'    : None,
            'expirationtime'   : None,
            'graceid'          : self.graceid,
            'grb_offline_json' : None,
            'grb_online_json'  : None,
            'labels'           : self.dictionary['labels'].keys(),
            'loggermessages'   : [],
            'pipeline'         : self.dictionary['pipeline']
        })  
    #-----------------------------------------------------------------------
    # ifosCheck
    #-----------------------------------------------------------------------
    def ifosCheck(self):
        ifos = self.data['instruments']
        res = len(ifos) > 1 # to neglect single IFO triggers 
        self.data['ifosCheckresult'] = res
        if not(res):
            self.client.writeLog(self.graceid, 'AP: Candidate event rejected due to Single IFO')
            self.data['ifoslogkey'] = 'yes'
            message = '{0} -- {1} -- Rejecting due to Single IFO {2}'.format(convertTime(), self.graceid, ifos[0])
            if loggerCheck(self.data, message)==False:
                self.logger.info(message)
        return res

    #-----------------------------------------------------------------------
    # farCheck
    #-----------------------------------------------------------------------
    def __get_farthresh__(self, pipeline, search, config):
        try:
            return config.getfloat('farCheck', 'farthresh[{0}.{1}]'.format(pipeline, search))
        except:
            return config.getfloat('farCheck', 'default_farthresh')

    def farCheck(self):
        '''
        checks to see if the far of the event candidate is less than the threshold
        '''
        farCheckresult = self.data['farCheckresult']
        if farCheckresult!=None:
            return farCheckresult
        else:
            far       = self.data['far']
            pipeline  = self.data['pipeline']
            search    = self.data['search']
            farthresh = self.__get_farthresh__(pipeline, search, self.config)
            if far >= farthresh:
                self.client.writeLog(self.graceid, 'AP: Candidate event rejected due to large FAR. {0} >= {1}'.format(far, farthresh), tagname='em_follow')
                self.data['farlogkey'] = 'yes'
                message = '{0} -- {1} -- Rejected due to large FAR. {2} >= {3}'.format(convertTime(), self.graceid, far, farthresh)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                    self.data['farCheckresult'] = False
                else:
                    pass
                return False
            elif far==None:
                self.client.writeLog(self.graceid, 'AP: Candidate event is missing FAR.', tagname='em_follow')
                self.data['farlogkey'] = 'yes'
                message = '{0} -- {1} -- Candidate event is missing FAR.'.format(convertTime(), self.graceid)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                    self.data['farCheckresult'] = False
                else:
                    pass
                return False
            elif far < farthresh:
                self.client.writeLog(self.graceid, 'AP: Candidate event has low enough FAR. {0} < {1}'.format(far, farthresh), tagname='em_follow')
                self.data['farlogkey'] = 'yes'
                message = '{0} -- {1} -- Low enough FAR. {2} < {3}'.format(convertTime(), self.graceid, far, farthresh)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                    self.data['farCheckresult'] = True
                else:
                    pass
                return True

    #-----------------------------------------------------------------------
    # labelCheck
    #-----------------------------------------------------------------------
    def labelCheck(self):
        '''
        checks whether event has either INJ or DQV label. it will treat INJ as a real event or not depending on config setting
        '''
        labels = self.data['labels']
        if checkLabels(labels, self.config) > 0:
            message = '{0} -- {1} -- Ignoring event due to INJ or DQV label.'.format(convertTime(), self.graceid)
            if loggerCheck(self.data, message)==False:
                self.logger.info(message)
                self.data['labelCheckresult'] = False
            else:
                pass
            return False
        else:
            self.data['labelCheckresult'] = True
            return True

    #-----------------------------------------------------------------------
    # injectionCheck
    #-----------------------------------------------------------------------
    def injectionCheck(self):
        injectionCheckresult = self.data['injectionCheckresult']
        if injectionCheckresult!=None:
            return injectionCheckresult
        else:
            eventtime = float(self.data['gpstime'])
            time_duration = self.config.getfloat('injectionCheck', 'time_duration')
            from raven.search import query
            th = time_duration
            tl = -th
            Injections = query('HardwareInjection', eventtime, tl, th)
            self.data['injectionsfound'] = len(Injections)
            hardware_inj = self.config.get('labelCheck', 'hardware_inj')
            if len(Injections) > 0:
                if hardware_inj=='no':
                    self.client.writeLog(self.graceid, 'AP: Ignoring new event because we found a hardware injection +/- {0} seconds of event gpstime.'.format(th), tagname = "em_follow")
                    self.data['injectionlogkey'] = 'yes'
                    message = '{0} -- {1} -- Ignoring new event because we found a hardware injection +/- {2} seconds of event gpstime.'.format(convertTime(), self.graceid, th)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                        self.data['injectionCheckresult'] = False
                    else:
                        pass
                    return False
                else:
                    self.client.writeLog(self.graceid, 'AP: Found hardware injection +/- {0} seconds of event gpstime but treating as real event in config.'.format(th), tagname = "em_follow")
                    self.data['injectionlogkey'] = 'yes'
                    message = '{0} -- {1} -- Found hardware injection +/- {2} seconds of event gpstime but treating as real event in config.'.format(convertTime(), self.graceid, th)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                        self.data['injectionCheckresult'] = True
                    else:
                        pass
                    return True
            elif len(Injections)==0:
                self.client.writeLog(self.graceid, 'AP: No hardware injection found near event gpstime +/- {0} seconds.'.format(th), tagname="em_follow")
                self.data['injectionlogkey'] = 'yes'
                message = '{0} -- {1} -- No hardware injection found near event gpstime +/- {2} seconds.'.format(convertTime(), self.graceid, th)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                    self.data['injectionCheckresult'] = True
                else:
                    pass
                return True

    #-----------------------------------------------------------------------
    # have_lvem_skymapCheck
    #-----------------------------------------------------------------------
    def have_lvem_skymapCheck(self):
        '''
        checks whether there is an lvem tagged skymap that has not been sent in an alert
        '''
        # this function should only return True or None, never False
        # if return True, we have a new lvem skymap
        # otherwise, add this Check to queueByGraceID
        currentstate = self.data['currentstate']
        lvemskymaps  = self.data['lvemskymaps'].keys()
        if currentstate=='preliminary_to_initial':
            if len(lvemskymaps)>=1:
                self.data['have_lvem_skymapCheckresult'] = True
                skymap = sorted(lvemskymaps)[-1]
                skymap = re.findall(r'-(\S+)', skymap)[0]
                message = '{0} -- {1} -- Initial skymap tagged lvem {2} available.'.format(convertTime(), self.graceid, skymap)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                else:
                    pass
                return True
            else:
                self.data['have_lvem_skymapCheckresult'] = None
                return None
        elif (currentstate=='initial_to_update' or currentstate=='complete'):
            if len(lvemskymaps)>=2:
                if lvemskymaps[-1]!=self.data['lastsentskymap']:
                    self.data['have_lvem_skymapCheckresult'] = True
                    skymap = sorted(lvemskymaps)[-1]
                    skymap = re.findall(r'-(\S+)', skymap)[0]
                    message = '{0} -- {1} -- Update skymap tagged lvem {2} available.'.format(convertTime(), self.graceid, skymap)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                    else:
                        pass
                    return True
                else:
                    self.data['have_lvem_skymapCheckresult'] = None
                    return None
            else:
                self.data['have_lvem_skymapCheckresult'] = None
                return None

    #-----------------------------------------------------------------------
    # idq_joint_fapCheck
    #-----------------------------------------------------------------------
    def __get_idqthresh__(self, pipeline, search, config):
        try:
            return config.getfloat('idq_joint_fapCheck', 'idqthresh[{0}.{1}]'.format(pipeline, search))
        except:
            return config.getfloat('idq_joint_fapCheck', 'default_idqthresh')

    def __compute_joint_fap_values__(self, config):
        idqvalues = self.data['idqvalues']
        jointfapvalues = self.data['jointfapvalues']
        idq_pipelines = config.get('idq_joint_fapCheck', 'idq_pipelines')
        idq_pipelines = idq_pipelines.replace(' ', '')
        idq_pipelines = idq_pipelines.split(',')
        for idqpipeline in idq_pipelines:
            pipeline_values = []
            for key in idqvalues.keys():
                if idqpipeline in key:
                    pipeline_values.append(idqvalues[key])
            jointfapvalues[idqpipeline] = functools.reduce(operator.mul, pipeline_values, 1)

    def idq_joint_fapCheck(self):
        group      = self.data['group']
        ignore_idq = self.config.get('idq_joint_fapCheck', 'ignore_idq')
        idq_joint_fapCheckresult = self.data['idq_joint_fapCheckresult']
        if idq_joint_fapCheckresult!=None:
            return idq_joint_fapCheckresult
        elif group in ignore_idq:
            # self.logger.info('{0} -- {1} -- Not using idq checks for events with group(s) {2}.'.format(convertTime(), self.graceid, ignore_idq))
            self.data['idq_joint_fapCheckresult'] = True
            return True
        else:
            pipeline       = self.data['pipeline']
            search         = self.data['search']
            idqthresh      = self.__get_idqthresh__(pipeline, search, self.config)
            self.__compute_joint_fap_values__(self.config)
            idqvalues      = self.data['idqvalues']
            idqlogkey      = self.data['idqlogkey']
            instruments    = self.data['instruments']
            jointfapvalues = self.data['jointfapvalues']
            idq_pipelines  = self.config.get('idq_joint_fapCheck', 'idq_pipelines')
            idq_pipelines  = idq_pipelines.replace(' ', '')
            idq_pipelines  = idq_pipelines.split(',')
            if len(idqvalues)==0:
                message = '{0} -- {1} -- Have not gotten all the minfap values yet.'.format(convertTime(), self.graceid)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                else:
                    pass
                return None
            elif (0 < len(idqvalues) < (len(idq_pipelines)*len(instruments))):
                message = '{0} -- {1} -- Have not gotten all the minfap values yet.'.format(convertTime(), self.graceid)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                else:
                    pass
                if (min(idqvalues.values() and jointfapvalues.values()) < idqthresh):
                    if idqlogkey=='no':
                        self.client.writeLog(self.graceid, 'AP: Finished running iDQ checks. Candidate event rejected because incomplete joint min-FAP value already less than iDQ threshold. {0} < {1}'.format(min(idqvalues.values() and jointfapvalues.values()), idqthresh), tagname='em_follow')
                        self.data['idqlogkey']='yes'
                    message = '{0} -- {1} -- iDQ check result: {2} < {3}'.format(convertTime(), self.graceid, min(idqvalues.values() and jointfapvalues.values()), idqthresh)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                        self.data['idq_joint_fapCheckresult'] = False
                    else:
                        pass
                    #self.client.writeLabel(self.graceid, 'DQV') [apply DQV in parseAlert when return False]
                    return False
            elif (len(idqvalues) > (len(idq_pipelines)*len(instruments))):
                message = '{0} -- {1} -- Too many minfap values in idqvalues dictionary.'.format(convertTime(), self.graceid)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                else:
                    pass
            else:
                message = '{0} -- {1} -- Ready to run iDQ checks.'.format(convertTime(), self.graceid)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
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
                    message = '{0} -- {1} -- Got joint_fap = {2} for iDQ pipeline {3}.'.format(convertTime(), self.graceid, jointfap, idqpipeline)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                    else:
                        pass
                if min(jointfapvalues.values()) > idqthresh:
                    if idqlogkey=='no':
                        self.client.writeLog(self.graceid, 'AP: Finished running iDQ checks. Candidate event passed iDQ checks. {0} > {1}'.format(min(jointfapvalues.values()), idqthresh), tagname = 'em_follow')
                        self.data['idqlogkey']='yes'
                    message = '{0} -- {1} -- Passed iDQ check: {2} > {3}.'.format(convertTime(), self.graceid, min(jointfapvalues.values()), idqthresh)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                        self.data['idq_joint_fapCheckresult'] = True
                    else:
                        pass
                    return True
                else:
                    if idqlogkey=='no':
                        self.client.writeLog(self.graceid, 'AP: Finished running iDQ checks. Candidate event rejected due to low iDQ FAP value. {0} < {1}'.format(min(jointfapvalues.values()), idqthresh), tagname = 'em_follow')
                        self.data['idqlogkey'] = 'yes'
                    message = '{0} -- {1} -- iDQ check result: {2} < {3}'.format(convertTime(), self.graceid, min(jointfapvalues.values()), idqthresh)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                        self.data['idq_joint_fapCheckresult'] = False
                    else:
                        pass
                    #self.client.writeLabel(self.graceid, 'DQV') [apply DQV in parseAlert when return False]
                    return False

    #-----------------------------------------------------------------------
    # operator_signoffCheck
    #-----------------------------------------------------------------------
    def operator_signoffCheck(self):
        operator_signoffCheckresult = self.data['operator_signoffCheckresult']
        if operator_signoffCheckresult!=None:
            return operator_signoffCheckresult
        else:
            instruments      = self.data['instruments']
            operatorlogkey   = self.data['operatorlogkey']
            operatorsignoffs = self.data['operatorsignoffs']
            if len(operatorsignoffs) < len(instruments):
                if 'NO' in operatorsignoffs.values():
                    if operatorlogkey=='no':
                        self.client.writeLog(self.graceid, 'AP: Candidate event failed operator signoff check.', tagname = 'em_follow')
                        self.data['operatorlogkey'] = 'yes'
                        # self.client.writeLabel(self.graceid, 'DQV') [apply DQV in parseAlert when return False]
                    self.data['operator_signoffCheckresult'] = False
                    return False
                else:
                    message = '{0} -- {1} -- Not all operators have signed off yet.'.format(convertTime(), self.graceid)
                    if loggerCheck(self.data, message)==False:
                        self.logger.info(message)
                    else:
                        pass
            else:
                if 'NO' in operatorsignoffs.values():
                    if operatorlogkey=='no':
                        self.client.writeLog(self.graceid, 'AP: Candidate event failed operator signoff check.', tagname = 'em_follow')
                        self.data['operatorlogkey'] = 'yes'
                        #self.client.writeLabel(self.graceid, 'DQV') [apply DQV in parseAlert when return False]
                    self.data['operator_signoffCheckresult'] = False
                    return False
                else:
                    if operatorlogkey=='no':
                        message = '{0} -- {1} -- Candidate event passed operator signoff check.'.format(convertTime(), self.graceid)
                        if loggerCheck(self.data, message)==False:
                            self.logger.info(message)
                        else:
                            pass
                        self.client.writeLog(self.graceid, 'AP: Candidate event passed operator signoff check.', tagname = 'em_follow')
                        self.data['operatorlogkey'] = 'yes'
                    self.data['operator_signoffCheckresult'] = True
                    return True

    #-----------------------------------------------------------------------
    # advocate_signoffCheck
    #-----------------------------------------------------------------------
    def advocate_signoffCheck(self):
        advocate_signoffCheckresult = self.data['advocate_signoffCheckresult']
        if advocate_signoffCheckresult!=None:
            return advocate_signoffCheckresult
        else:
            advocatelogkey = self.data['advocatelogkey']
            advocatesignoffs = self.data['advocatesignoffs']
            if len(advocatesignoffs)==0:
                message = '{0} -- {1} -- Advocates have not signed off yet.'.format(convertTime(), self.graceid)
                if loggerCheck(self.data, message)==False:
                    self.logger.info(message)
                else:
                    pass
            elif len(advocatesignoffs) > 0:
                if 'NO' in advocatesignoffs:
                    if advocatelogkey=='no':
                        self.client.writeLog(self.graceid, 'AP: Candidate event failed advocate signoff check.', tagname = 'em_follow')
                        self.data['advocatelogkey'] = 'yes'
                        #self.client.writeLabel(self.graceid, 'DQV') [apply DQV in parseAlert when return False]
                    self.data['advocate_signoffCheckresult'] = False
                    return False
                else:
                    if advocatelogkey=='no':
                        message = '{0} -- {1} -- Candidate event passed advocate signoff check.'.format(convertTime(), self.graceid)
                        if loggerCheck(self.data, message)==False:
                            logger.info(message)
                        else:
                            pass
                        self.client.writeLog(self.graceid, 'AP: Candidate event passed advocate signoff check.', tagname = 'em_follow')
                        self.data['advocatelogkey'] = 'yes'
                    self.data['advocate_signoffCheckresult'] = True
                    return True

#-----------------------------------------------------------------------
# Saving event dictionaries
#-----------------------------------------------------------------------
def saveEventDicts(approval_processorMPfiles):
    '''
    saves eventDicts (the dictonary of event dictionaries) to a pickle file and txt file
    '''
    ### figure out filenames, etc.
    ### FIXME: THIS SHOULD NOT BE HARD CODED! Instead, use input arguments
    homedir = os.path.expanduser('~')
    pklfilename = '{0}{1}/EventDicts.p'.format(homedir, approval_processorMPfiles)
    txtfilename = '{0}{1}/EventDicts.txt'.format(homedir, approval_processorMPfiles)

    ### write pickle file
    file_obj = open(pklfilename, 'wb')
    pickle.dump(eventDictionaries, file_obj) # note: we save eventDictionaries rather than eventDicts because we run into pickling errors with the instances saved in eventDicts
    file_obj

    ### write txt file
    file_obj = open(txtfilename, 'w')
    for graceid in sorted(eventDictionaries.keys()): ### iterate through graceids
        file_obj.write('{0}\n'.format(graceid))
        event_dict = eventDictionaries[graceid]

        for key in sorted(event_dict.keys()): ### iterate through keys for this graceid
            if key!='loggermessages':
                file_obj.write('    {0}: {1}\n'.format(key, event_dict[key]))
        file_obj.write('\n')
    file_obj.close()

#-----------------------------------------------------------------------
# Loading event dictionaries
#-----------------------------------------------------------------------
def loadEventDicts(approval_processorMPfiles):
    '''
    loads eventDictionaries (the dictionary of event dictionaries) to do things like resend VOEvents for an event candidate
    '''
    homedir = os.path.expanduser('~')
    pklname = '{0}{1}/EventDicts.p'.format(homedir, approval_processorMPfiles)

    if os.path.exists(pklname): ### check to see if the file actually exists
        file_obj = open(pklname, 'rb')
        global eventDictionaries
        eventDictionaries = pickle.load(file_obj) ### if something fails here, we want to know about it!
        file_obj.close()

#-----------------------------------------------------------------------
# Load logger
#-----------------------------------------------------------------------
def loadLogger(config):
    '''
    sets up logger.
    assumes the config has already been set up! if it hasn't been, please run loadConfig before running loadLogger
    '''
    global logger
    logger = logging.getLogger('approval_processorMP')
    approval_processorMPfiles = config.get('general', 'approval_processorMPfiles')
    logfile = config.get('general', 'approval_processorMP_logfile')
    homedir = os.path.expanduser('~')
    logging_filehandler = logging.FileHandler('{0}{1}{2}'.format(homedir, approval_processorMPfiles, logfile))
    logging_filehandler.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging_filehandler)
    return logger

#-----------------------------------------------------------------------
# Load config
#-----------------------------------------------------------------------
def loadConfig():
    '''
    loads the childConfig-approval_processorMP.ini
    it will prompt the user if they want to use the one on the gracedb.processor machine, or if they want to specify a specific one
    '''
    config = ConfigParser.SafeConfigParser()
    default = raw_input('do you want to use the default childConfig-approval_processorMP.ini in the grinch installation? options are yes or no\n')
    if default=='yes':
        #config.read('/home/gracedb.processor/public_html/monitor/approval_processorMP/files/childConfig-approval_processorMP.ini')
        config.read('/home/gracedb.processor/opt/etc/childConfig-approval_processorMP.ini')
    elif default=='no':
        config.read('{0}/childConfig-approval_processorMP.ini'.format(raw_input('childConfig-approval_processorMP.ini file directory? *do not include forward slash at end*\n')))
    else:
        print 'sorry. options were yes or no. try again'
    return config

#-----------------------------------------------------------------------
# Make config_dict 
#-----------------------------------------------------------------------
def makeConfigDict(config):
    client                  = config.get('general', 'client')
    force_all_internal      = config.get('general', 'force_all_internal')
    preliminary_internal    = config.get('general', 'preliminary_internal')
    hardware_inj            = config.get('labelCheck', 'hardware_inj')
    default_farthresh       = config.getfloat('farCheck', 'default_farthresh')
    humanscimons            = config.get('operator_signoffCheck', 'humanscimons')

    ### extract options about advocates
    advocates      = config.get('advocate_signoffCheck', 'advocates')

    ### extract options about idq
    ignore_idq        = config.get('idq_joint_fapCheck', 'ignore_idq')
    default_idqthresh = config.getfloat('idq_joint_fapCheck', 'default_idqthresh')

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
        'client'              : client
    }
    return configdict

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

def is_external_trigger(alert):
    '''a function that looks to see if lvalert regards an external GRB trigger or not'''
    graceid  = alert['uid']
    if re.match('E', graceid):
        return True
    if alert.has_key('object'): # noticed that label alert_types do not have 'object' key
        group    = alert['object']['group'] if alert['object'].has_key('group') else '' # lvalerts produced for uploaded comments dont have group,
                   # pipeline, or search info
        pipeline = alert['object']['pipeline'] if alert['object'].has_key('pipeline') else ''
        search   = alert['object']['search'] if alert['object'].has_key('search') else ''
        if group=='External':
            return True
        elif pipeline=='Swift' or pipeline=='Fermi' or pipeline=='SNEWS':
            return True
        elif search=='GRB':
            return True
    else:
        return False
    
def checkLabels(labels, config):
    hardware_inj = config.get('labelCheck', 'hardware_inj')
    if hardware_inj == 'yes':
        badlabels = ['DQV', 'EM_Throttled', 'EM_Superseded', 'H1NO', 'L1NO', 'ADVNO']
    else:
        badlabels = ['DQV', 'EM_Throttled', 'EM_Superseded', 'INJ', 'H1NO', 'L1NO', 'ADVNO']
    intersectionlist = list(set(badlabels).intersection(labels))
    return len(intersectionlist)

def record_coinc_info(event_dict, comment, alert, logger):
    graceid = event_dict['graceid']
    # is this a log comment from PyGRB or X-pipeline for an external trigger?
    if is_external_trigger(alert)==True:
        coinc_info = re.findall('(.*): Significant event in on-source \(FAP = (.*) for the most significant event\)', comment)
        coinc_pipeline = coinc_info[0][0]
        coinc_fap = float(coinc_info[0][1])
        message = '{0} -- {1} -- {2} coincidence found with FAP {3}.'.format(convertTime(), graceid, coinc_pipeline, coinc_fap)
        if loggerCheck(event_dict, message)==False:
            logger.info(message)
        else:
            pass
        return coinc_pipeline, coinc_fap
    # if this a log comment from RAVEN
    else:
        coinc_info = re.findall('Temporal coincidence with external trigger (.*)>(.*)<(.*) gives a coincident FAR = (.*) Hz', comment) # this parsing looks messy but only because the raw string we need to parse contains html code
        exttrig = coinc_info[0][1]
        event_dict['external_trigger'] = exttrig
        coinc_far = coinc_info[0][3]
        message = '{0} -- {1} -- RAVEN coincidence found with FAR {2}. External trigger {3}.'.format(convertTime(), graceid, coinc_far, exttrig)
        if loggerCheck(event_dict, message)==False:
            logger.info(message)
        else:
            pass
        return exttrig, coinc_far

def record_em_bright(event_dict, comment, logger):
    graceid = event_dict['graceid']
    em_bright_info = {}
    ProbHasNS, RemnantThresh, ProbHasRemnant = re.findall('The probability of second object being a neutron star  = (.*)% \n  The probability of remnant mass outside the black hole in excess of (.*) M_sun = (.*)% \n', comment)[0]
    em_bright_info['ProbHasNS'] = float(ProbHasNS)/100
    em_bright_info['ProbHasRemnant'] = float(ProbHasRemnant)/100
    em_bright_info['RemnantMassThreshInM_Sun'] = float(RemnantThresh)
    event_dict['em_bright_info'] = em_bright_info
    message = '{0} -- {1} -- EM Bright probabilities recorded.'.format(convertTime(), graceid)
    if loggerCheck(event_dict, message)==False:
        logger.info(message)
    else:
        pass

def record_label(event_dict, label):
    labels = event_dict['labels']
    graceid = event_dict['graceid']
    labels.append(label)
    message = '{0} -- {1} -- Got {2} label.'.format(convertTime(), graceid, label)
    if loggerCheck(event_dict, message)==False:
        logger.info(message)
    else:
        pass

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

#-----------------------------------------------------------------------
# process_alert
#-----------------------------------------------------------------------
def process_alert(event_dict, voevent_type, client, config, logger, set_internal='do nothing'):
    graceid = event_dict['graceid']
    pipeline = event_dict['pipeline']
    voeventerrors = event_dict['voeventerrors']
    voevents = event_dict['voevents']

    # setting default internal value settings for alerts
    force_all_internal = config.get('general', 'force_all_internal')
    if force_all_internal=='yes':
        internal = 1
    else:
        internal = 0

    open_default_farthresh = config.getfloat('farCheck', 'open_default_farthresh')
    far = event_dict['far']
    if far < open_default_farthresh: # the far is below the open alert default far threshold so we send an open alert
        open_alert = 1
    else:
        open_alert = 0

    if voevent_type=='preliminary':
        if force_all_internal=='yes':
            internal = 1
        else:
            if pipeline in preliminary_internal:
                internal = 1
            else:
                internal = 0
        vetted = 0 # default value for preliminary alerts
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
            vetted = 1
            skymap_filename = None
            skymap_type = None
            skymap_image_filename = None
        else: # we have not sent voevents before, no need for retraction
            return

    if (voevent_type=='initial' or voevent_type=='update'):
        vetted = 1 # all initial and update alerts have been human vetted by definition
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
        eventDicts[graceid].injectionCheck()
        hardware_inj = event_dict['injectionsfound']
    else:
        hardware_inj = injectionsfound

    # did we identify a coincident GRB trigger?
    if event_dict['external_trigger'] != None:
        CoincComment = 1
    else:
        CoincComment = 0

    # is EM-Bright information available? if so, include here
    if event_dict.has_key('em_bright_info'):
        EM_Bright = event_dict['em_bright_info']
        ProbHasNS = EM_Bright['ProbHasNS']
        ProbHasRemnant = EM_Bright['ProbHasRemnant']
    else:
        ProbHasNS = None
        ProbHasRemnant = None

    if set_internal=='yes': # this will override all 'internal' logic above and set internal = 1
        internal = 1
    elif set_internal=='no': # this will override all 'internal' logic above and set internal = 0
        internal = 0
    elif set_internal=='do nothing': # this will set 'internal' as whatever the config logic has it to be above
        internal = internal

    thisvoevent = '(internal,vetted,open_alert,hardware_inj,skymap):({0},{1},{2},{3},{4})-'.format(internal, vetted, open_alert, hardware_inj, skymap_filename) + voevent_type
    # check if we sent this voevent before
    if thisvoevent in str(voevents):
        message = '{0} -- {1} -- This {2} VOEvent has been sent previously.'.format(convertTime(), graceid, voevent_type)
        if loggerCheck(event_dict, message)==False:
            logger.info(message)
        else:
            pass
        return
    else: # we have not sent this alert before so continue
        pass
#    if (len(voevents) > 0) and (thisvoevent in sorted(voevents)[-1]):
#        if voevent_type=='preliminary':
#            if skymap_filename!=event_dict['lastsentpreliminaryskymap']:
#                pass # we have not sent a preliminary alert with this skymap
#            else:
#                return
#        else:
#            return
#    else:
#        pass

    logger.info('{0} -- {1} -- Creating {2} VOEvent file locally.'.format(convertTime(), graceid, voevent_type))
    voevent = None
    thisvoevent = '{0}-'.format(len(voevents) + 1) + thisvoevent

    try:
        r = client.createVOEvent(graceid, voevent_type, skymap_filename = skymap_filename, skymap_type = skymap_type, 
                skymap_image_filename = skymap_image_filename, internal = internal, vetted = vetted, open_alert = open_alert, 
                hardware_inj = hardware_inj, CoincComment = CoincComment, ProbHasNS = ProbHasNS, ProbHasRemnant = ProbHasRemnant)       
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
            if (voevent_type=='preliminary'):
                event_dict['lastsentpreliminaryskymap'] = skymap_filename
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
            thisvoevent = '{0}-(internal,vetted,open_alert,hardware_inj,skymap):({1},{2},{3},{4},{5})-'.format(len(voeventerrors) + 1, internal, vetted, open_alert, hardware_inj, skymap_filename) + voevent_type
            voeventerrors.append(thisvoevent)
            return 'voeventerrors, {0}'.format(thisvoevent)

#-----------------------------------------------------------------------
# in the case we need to re-send alerts from outside the running
# approval_processorMP instance
#-----------------------------------------------------------------------
def resend_alert():
    # load config and set up client
    config = loadConfig()
    # set up client
    client = config.get('general', 'client')
    approval_processorMPfiles = config.get('general', 'approval_processorMPfiles')
    print 'got client: {0}'.format(client)
    g = initGraceDb('{0}'.format(client))

    # set up logger
    logger = loadLogger(config)

    # prompt for graceid
    graceid = str(raw_input('graceid:\n'))

    # prompt for voevent_type
    voevent_type = str(raw_input('voevent_type: (options are preliminary, initial, update, retraction)\n'))

    # prompt for what the 'internal' value should be -- whether the alert should be kept internal or not
    set_internal = str(raw_input('set_internal: (options are yes, no, do nothing)\nyes means alert will be kept internal\nno means alert will be sent out\ndo nothing means approval_processorMP will use specifications from the config file to determine what internal should be\n'))

    # make a fresh dictionary, send alert
    event_dict = EventDict() # create a new instance of the EventDict class with is a blank event_dict
    configdict = makeConfigDict(config) # make a configdict needed for the setup
    event_dict.setup(g.events(graceid).next(), graceid, configdict, g, config, logger) # filling in the basics about the event
    event_dict.update() # update the event_dict with signoffs and iDQ info, etc
    eventDicts[graceid] = event_dict
    eventDictionaries[graceid] = event_dict.data
    if set_internal=='yes':
        print 'internal will be set to 1'
        response = process_alert(event_dict.data, voevent_type, g, config, logger, set_internal='yes')
    elif set_internal=='no':
        print 'internal will be set to 0'
        response = process_alert(event_dict.data, voevent_type, g, config, logger, set_internal='no')
    elif set_internal=='do nothing':
        response = process_alert(event_dict.data, voevent_type, g, config, logger)
    # to edit event_dict in parseAlert later
    response = re.findall(r'(.*), (.*)', response)

    sp.Popen('/usr/bin/gracedb log --tag-name=\'analyst_comments\' {0} \'resent VOEvent {1} in {2}\''.format(graceid, response[0][1], response[0][0]), stdout=sp.PIPE, shell=True)
    print 'voeventerrors: {0}'.format(event_dict['voeventerrors'])
    # prompt for exit
    exit_option = raw_input('exit: (options are yes or no)\n')
    if exit_option=='yes':
        exit()
    elif exit_option=='no':
        pass

def createTestEventDict(graceid):
    config = loadConfig()
    client = config.get('general', 'client')
    g = initGraceDb(client)
    configdict = makeConfigDict(config)
    logger = loadLogger(config)
    event_dict = EventDict()
    event_dict.setup(g.events(graceid).next(), graceid, configdict, g, config, logger)
    event_dict.update()
    eventDicts[graceid] = event_dict
    eventDictionaries[graceid] = event_dict.data
    return event_dict.data
