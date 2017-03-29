description = """commands for approval_processorMP.py
NOTE: this module relies heavily on inheritance from classes defined in lvalertMP.lvalert.commands"""
author = "Min-A Cho (mina19@umd.edu), Reed Essick (reed.essick@ligo.org)"

from queueItemsAndTasks import generate_ThrottleKey
from lvalertMP.lvalert import lvalertMPutils as utils
from lvalertMP.lvalert import commands
from lvalertMP.lvalert.commands import knownCommands, requiredKWargs, forbiddenKWargs, parseCommand

from numpy import infty
import logging

#-------------------------------------------------
# Define ResetThrottle Command, CommandQueueItem and Task
#-------------------------------------------------
class ResetThrottle(commands.Command):
    '''
    Resets a throttled pipeline
    '''
    name = 'resetThrottle'

    def __init__(self, **kwargs):
        super(ResetThrottle, self).__init__(command_type=self.name, **kwargs)

class ResetThrottleItem(commands.CommandQueueItem):
    '''
    QueueItem that resets pipeline throttles
    '''
    name = 'resetThrottle'
    description = 'resets throttled PipelineThrottle queueItems by calling the reset() method'

class ResetThrottleTask(commands.CommandTask):
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
        ###print in the logger
        logger  = logging.getLogger('%s.%s'%(self.logTag, self.name)) ### want this to also propagate to interactiveQueue's logger
        handler = logging.StreamHandler() ### we don't format this so that it prints exactly as supplied
                                          ### however, interactiveQueue's handler *will* be formatted nicely 
        logger.addHandler( handler )

        ### determine the throttleKey associated with this command
        throttleKey = generate_ThrottleKey(kwargs['group'], kwargs['pipeline'], search=kwargs['search'] if kwargs.has_kwy('search') else None)

        ### print to logger
        logger.info('received PipelineThrottle throttleKey: {0}'.format(throttleKey ))
        ### get the correct queueByGraceID sortedQueue
        if self.queueByGraceID.has_key(throttleKey):
            item = self.queueByGraceID[throttleKey][0]
            logger.info('Found PipelineThrottle QueueItem, calling reset method')
            logger.info('Before reset, events list: {0}'.format(item.events))
            item.reset()
            logger.info('After reset, events list: {0}'.format(item.events))

            ### after calling item.reset(), item.complete is set to True. 
            ### This means that interactiveQueue will automatically skip it and we don't need to touch the expiration

            ### we do need to pop this key from self.queueByGraceId
            self.queueByGraceID.pop(throttleKey)

            ### we also need to increment the counter of complete items within self.queue
            self.queue.complete += item.complete

            ### NOTE: we leave a reference to this item within self.queue, but that's perfectly acceptable.
            ### by design, this is what we're supposed to do so that we do not have to resort self.queue or
            ### identify the index associated with this item within self.queue 

        else:
            logger.info('Did not find PipelineThrottle QueueItem in QueueByGraceid')

#-------------------------------------------------
# update dictionaries within lvalertMP.lvalert.commands
#-------------------------------------------------

commands.__cid__['resetThrottle'] = ResetThrottle
commands.__qid__['resetThrottle'] = ResetThrottleItem
commands.__tid__['resetThrottle'] = ResetThrottleTask
