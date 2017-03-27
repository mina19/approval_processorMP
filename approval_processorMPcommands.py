description = """commands for approval_processorMP.py
NOTE: this module relies heavily on inheritance from classes defined in lvalertMP.lvalert.commands"""
author = "Min-A Cho (mina19@umd.edu), Reed Essick (reed.essick@ligo.org)"

from queueItemsAndTasks import generate_ThrottleKey
from lvalertMP.lvalert import lvalertMPutils as utils

import json
import sys
from numpy import infty
import types
import time
import logging

### XXX: IMPORTANT NOTE! Had to explicitly copy over Command, CommandQueueItem,
### and CommandTask objects because the script approvalprocessor_commandMP makes
### calls to the Command write() method, which in turn calls to __cid__. But, if
### you import over the Command object, your __cid__ in the lvalertMP.lvalert.commands
### file does not have the resetThrottle command in it.

class Command(object):
    '''
    an object based representation of Commands. 
    Each specific command should inherit from from this and provide the following functionality
    '''
    name = 'command'

    def __init__(self, command_type='command', **kwargs):
        self.data = { 'uid'        : 'command',
                      'alert_type' : command_type,
                      'object'     : kwargs,
                    }

    def checkObject(self):
        '''
        ensures that all of the required kwargs are present in self.data['object']
        if something is missing, we raise a KeyError
        also checks to make sure that no forbidden_kwarg is present.
        if one is, we raise a KeyError
        '''
        kwargs = self.data['object']
        for kwarg in __tid__[self.name].required_kwargs: ### check to make sure we have everyting we need
            if not kwargs.has_key(kwarg):
                raise KeyError('Command=%s is missing required kwarg=%s'%(self.name, kwarg))
        for kwarg in __tid__[self.name].forbidden_kwargs: ### check to make sure we don't have anything forbidden
            if kwargs.has_key(kwarg):
                raise KeyError('Command=%s contains forbidden kwarg=%s'%(self.name, kwarg))

    def parse(self, alert):
        '''
        parse a json dictionary from an alert and store data locally
        '''
        if alert['alert_type']==self.name:
            self.data = alert
        else:
            raise ValueError('cannot parse an command with alert_type=%s within command=%s'%(alert['alert_type'], self.name))
        self.checkObject() ### ensure we have all the kwargs we need

    def write(self):
        '''
        write a json string that can be sent as an alert
        '''
        self.checkObject() ### ensure we have all the kwargs we need
        return json.dumps(self.data)

    def genQueueItems(self, queue, queueByGraceID, t0, logTag='iQ'):
        '''
        defines a list of QueueItems that need to be added to the queue
        uses automatic lookup via __qid__ to identify which QueueItem must be generated based on self.name
        '''
        self.checkObject() ### ensure we have all the kwargs we need
        return [ __qid__[self.name](t0, queue, queueByGraceID, logTag=logTag, **self.data['object']) ] ### look up the QueueItem via qid and self.name, then call the __init__ as needed

class CommandQueueItem(utils.QueueItem):
    '''
    A parent QueueItem for Commands. This class handles automatic lookup and Task instantiation.
    Most if not all children will simply overwrite the name and description attributes.
    '''
    name = 'command'
    description = 'parent of all command queue items. Implements automatic generation of associated Tasks, etc'

    def __init__(self, t0, queue, queueByGraceID, logTag='iQ', **kwargs):
        tasks = [ __tid__[self.name](queue, queueByGraceID, logTag="%s.%s"%(logTag, self.name), **kwargs) ] ### look up tasks automatically via name attribute

        if kwargs.has_key('graceid'): ### if attached to a graceid, associate it as such
            self.graceid = kwargs['graceid']

        super(CommandQueueItem, self).__init__(t0, tasks, logTag=logTag)

class CommandTask(utils.Task):
    '''
    A parent Task for commands. This class handles automatic identification of functionhandle using self.name. 
    Most children will simply overwrite name and description attributes and define a new method for their actual execution.
    '''
    name = 'command'
    description = "parent of all command tasks"

    required_kwargs  = []
    forbidden_kwargs = []

    def __init__(self, queue, queueByGraceID, logTag='iQ', **kwargs ):
        self.queue = queue
        self.queueByGraceID = queueByGraceID
        if kwargs.has_key('sleep'): ### if this is supplied, we use it
            timeout = kwargs['sleep']
        else:
            timeout = -infty ### default is to do things ASAP
        super(CommandTask, self).__init__(timeout, logTag=logTag, **kwargs) ### lookup function handle automatically using self.name
        self.checkKWargs() ### ensure we've set this up correctly. Should be redundant if we construct through Command.genQueueItems. 
                           ### supported in case we create QueueItems directly.
    def checkKWargs(self):
        '''
        checks to make sure we have all the kwargs we need and none of the ones we forbid
        if there's a problem, we raise a KeyError
        '''
        for kwarg in self.required_kwargs: ### check to make sure we have everyting we need. looks up lists within corresponding Command object
            if not self.kwargs.has_key(kwarg):
                raise KeyError('CommandTask=%s is missing required kwarg=%s'%(self.name, kwarg))

        for kwarg in self.forbidden_kwargs: ### check to make sure we don't have anything forbidden. looks up list within corresopnding Command object
            if self.kwargs.has_key(kwarg):
                raise KeyError('CommandTask=%s contains forbidden kwarg=%s'%(self.name, kwarg))

    def command(self, verbose=False, **kwargs):
        pass



#-------------------------------------------------
# Define ResetThrottle Command, CommandQueueItem and Task
#-------------------------------------------------
class ResetThrottle(Command):
    '''
    Resets a throttled pipeline
    '''
    name = 'resetThrottle'

    def __init__(self, **kwargs):
        super(ResetThrottle, self).__init__(command_type=self.name, **kwargs)

class ResetThrottleItem(CommandQueueItem):
    '''
    QueueItem that resets pipeline throttles
    '''
    name = 'resetThrottle'
    description = 'resets throttled PipelineThrottle queueItems by calling the reset() method'

class ResetThrottleTask(CommandTask):
    '''
    Task that resets PipelineThrottle queueItem by calling the reset() method
    '''
    name = 'resetThrottle'
    description = 'resets PipelineThrottle'

    required_kwargs  = ['group', 'pipeline']
    forbidden_kwargs = []

    def resetThrottle(self, verbose=False, **kwargs):
        '''
        generate the throttle key that will be used to reset the correct PipelineThrottle queueItem
        '''
        if kwargs.has_key('search'):
            throttleKey = generate_ThrottleKey(kwargs['group'], kwargs['pipeline'], kwargs['search'])
        else:
            throttleKey = generate_ThrottleKey(kwargs['group'], kwargs['pipeline'], '')
        ###print in the logger
        logger  = logging.getLogger('%s.%s'%(self.logTag, self.name)) ### want this to also propagate to interactiveQueue's logger
        handler = logging.StreamHandler() ### we don't format this so that it prints exactly as supplied
                                          ### however, interactiveQueue's handler *will* be formatted nicely 
        logger.addHandler( handler )

        ### print to logger
        logger.info('received PipelineThrottle throttleKey: {0}'.format(throttleKey ))
        ### get the correct queueByGraceID sortedQueue
        if self.queueByGraceID.has_key(throttleKey):
            item = self.queueByGraceID[throttleKey][0]
            logger.info('Found PipelineThrottle QueueItem, calling reset method')
            logger.info('Before reset, events list: {0}'.format(item.events))
            item.reset()
            logger.info('After reset, events list: {0}'.format(item.events))
            logger.info('Resorting the queue after setting expiration time to -infty')
            ### here we just set the expiration times to -infty and then the
            ### sortedqueue object will take care of executing the task and 
            ### clearing the queueItem from the sorted queue and queueByGraceID
            item.expiration = -infty
            item.tasks[0].expiration = -infty
            self.queue.resort()
            ### Nothing more to do here! features of interactive queue will take
            ### care of getting rid of the empty sortedqueue list in the queueByGraceID
        else:
            logger.info('Did not find PipelineThrottle QueueItem in QueueByGraceid')




#-------------------------------------------------
# define useful variables
#-------------------------------------------------

### set up dictionaries
__cid__ = {} ### Commands by their name attributes
__qid__ = {} ### QueueItems by their name attributes
__tid__ = {} ### Tasks by their name attributes
for x in vars().values():

    if isinstance(x, type):
        if issubclass(x, Command):
            __cid__[x.name] = x
        elif issubclass(x, CommandQueueItem):
            __qid__[x.name] = x
        elif issubclass(x, CommandTask):
            __tid__[x.name] = x

__cid__.pop('command') ### get rid of parent class because we shouldn't be calling it. It's really just a template...
__qid__.pop('command') ### get rid of parent class
__tid__.pop('command') ### get rid of parent class

### confirm that __cid__, __qid__, and __tid__ all have matching keys
assert (sorted(__cid__.keys()) == sorted(__qid__.keys())) and (sorted(__cid__.keys()) == sorted(__tid__.keys())), \
    "inconsistent name attributes within sets of defined Commands, CommandQueueItems, and CommandTasks"

#------------------------
# utilities for looking up info within private variables
#------------------------

def initCommand( name, **kwargs ):
    '''
    wrapper that instantiates Command objects
    '''
    if not __cid__.has_key(name):
        raise KeyError('Command=%s is not known'%name)
    return __cid__[name]( **kwargs )

#-----------

def knownCommands():
    '''
    returns a sorted list of known commands
    '''
    return sorted(__cid__.keys())

#-----------

def requiredKWargs( name ):
    '''
    returns the required KWargs for this command
    '''
    if not __tid__.has_key(name):
        raise KeyError('Command=%s is not known'%name)
    return __tid__[name].required_kwargs

#-----------

def forbiddenKWargs( name ):
    '''
    returns the forbidden KWargs for this command
    '''
    if not __tid__.has_key(name):
        raise KeyError('Command=%s is not known'%name)
    return __tid__[name].forbidden_kwargs

#-------------------------------------------------
# parseCommand
#-------------------------------------------------

def parseCommand( queue, queueByGraceID, alert, t0, logTag='iQ' ):
    '''
    a doppelganger for parseAlert that focuses on commands.
    this should be called from within parseAlert as needed
    '''
    if alert['uid'] != 'command':
        raise ValueError('I only know how to parse alerts with uid="command"')

    ### set up logger
    logger = logging.getLogger('%s.parseCommand'%logTag) ### want this to propagate to interactiveQueue's logger

    cmd = initCommand( alert['alert_type'] ) ### instantiate the Command object
    cmd.parse( alert ) ### parse the alert message

    for item in cmd.genQueueItems(queue, queueByGraceID, t0, logTag=logTag): ### add items to the queue
        queue.insert( item )
        if hasattr(item, 'graceid'):
            if not queueByGraceID.has_key(item.graceid):
                queueByGraceID[item.graceid] = utils.SortedQueue()
            queueByGraceID[item.graceid].insert( item )
        logger.debug( 'added Command=%s'%item.name )

    return 0 ### the number of new completed tasks in queue. 
             ### This is not strictly needed and is not captured and we should modify the attribute of SortedQueue directly
