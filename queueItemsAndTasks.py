description = "a module that holds definitions of all required QueueItem and Task extensions used within approval processor"
author = "Min-A Cho (mina19@umd.edu), Reed Essick (reed.essick@ligo.org)"

#-------------------------------------------------

from ligoMP.lvalert import lvalertMPutils as utils
import numpy as np

#-------------------------------------------------
# ForgetMeNow
# used to clean up local data when we no longer care about a particular GraceID
#-------------------------------------------------

class ForgetMeNow(utils.QueueItem):
    """
    sets the expiration time for GW event candidate using time of last lvalert
    """
    name = 'forget me now'
    description = 'upon execution delegates to RemoveFromEventDicts and CleanUpQueue in order to remove graceID from EventDict.EventDicts and any assoicated queue items'

    def __init__(self, t0, timeout, graceid, event_dicts, queue, queueByGraceID, logger):
        self.graceid = graceid ### required to look up and modify objects refering to this graceid. Also means interactiveQueue will manage queueByGraceID for us.
        self.event_dicts = event_dicts ### pointer to the big "dictionary of dictionaries" which keeps local records of events' states
        self.logger = logger ### used to redirect print statements
        tasks = [RemoveFromEventDicts(graceid, event_dicts, timeout, logger),  ### first task removes the event from the dict of dicts
                 CleanUpQueue(graceid, queue, queueByGraceID, timeout)                ### second task removes everything from the queues
                ]
        super(ForgetMeNow, self).__init__(t0, tasks) ### delegate instantiation to the parent class

    def setExpiration(self, t0, convertTime):
        '''
        updates the expiration of all tasks as well as of the QueueItem itself.
        we overwrite the parent's function because we also touch the event_dict
        '''
#        super(ForgetMeNow, self).setExpiration() ### delegate to parent to touch tasks and self.expiration -XXX throws an error: super has no attribute setExpiration()
        self.convertTime = convertTime
        for task in self.tasks:
            task.setExpiration(t0) ### update expiration of each task
        self.sortTasks() ### sorting tasks in the QueueItem. This automatically updates self.expiration
        self.event_dicts[self.graceid]['expirationtime'] = '{0} -- {1}'.format(self.expiration, convertTime(self.expiration)) ### records the expiration in local memory

class RemoveFromEventDicts(utils.Task):
    """
    first task that gets called by ForgetMeNow; it removes the graceID  event dictionary from EventDict.EventDicts
    """
    name = 'remove from event dicts'
    description = 'removes graceID event dictionary from self.event_dicts'

    def __init__(self, graceid, event_dicts, timeout, logger):
        self.graceid = graceid ### needed for lookup
        self.event_dicts = event_dicts ### pointer to the big "dictionary of dictionaries" which keeps local records of events' states
        self.logger = logger ### used to redirect print statements
        super(RemoveFromEventDicts, self).__init__(timeout, self.removeEventDict) ### delegate to the parent class

    def removeEventDict(self, verbose=False):
        """
        removes graceID event dictionary from self.event_dicts
        """
        self.logger.info('{0} -- {1} -- Removing event dictionary upon expiration time.'.format(convertTime(), self.graceid)) ### record that we're removing this
        self.event_dicts.pop(self.graceid) ### remove the graceid from the dict of dicts

class CleanUpQueue(utils.Task):
    """
    second task that gets called by ForgetMeNOw; it cleans up queueByGraceID and removes any Queue Item with self.graceid
    """
    name = 'clean up queue'
    description = 'cleans up queueByGraceID'

    def __init__(self, graceid, queue, queueByGraceID, timeout):
        self.graceid = graceid ### required for lookup
        self.queue = queue ### pointer for queue that is managed within interactiveQueue and passed to parseAlert
        self.queueByGraceID = queueByGraceID ### pointer to the queueByGraceID that is managed within interactiveQueue and passed to parseAlert
        super(CleanUpQueue, self).__init__(timeout, self.cleanUpQueue) ### delegate to parent class

    def cleanUpQueue(self, verbose=False):
        """
         cleans up queueByGraceID; removes any Queue Item with self.graceid
        """
        sortedQueue = self.queueByGraceID[self.graceid] ### extract the instance of sortded queue for this graceid
        queueItem = sortedQueue.pop(0) # this will return the instance of the ForgetMeNow class which is associated with this task
        while len(sortedQueue): ### remove the rest of the queueItems for this graceid and marke them complete
            nextQueueItem = sortedQueue.pop(0) ### remove the item
            nextQueueItem.complete = True ### mark as complete
            self.queue.complete += 1 ### increment self.queue's complete attribute to reflect that we marked this item as complete
        sortedQueue.insert(queueItem) # putting this queue item back in so that when interactiveQueue reaches the sorted queue associated with this self.graceid, it will not break

#-------------------------------------------------
# PipelineThrottle
# used to ignore certain pipelines when they submit too many events to GraceDB. 
# NOTE: this will not stop GraceDB from crashing but it will prevent approval processor from being overloaded
#-------------------------------------------------

class PipelineThrottle(utils.QueueItem):
    '''
    A throttle that determines which events approval processor will actually track.
    This is implemented so that pipelines which are behaving badly do not trigger alerts.
    All the actual manipulations of events and decision making are delegated to this class's single task: Throttle(lvalerMPutils.Task)

    assigns group_pipeline[_search] to self.graceid for easy lookup and management within queueByGraceID

    NOTE: we overwrite execute() and don't use the parent's __init__
        This means things may be fragile...
    '''
    name = 'pipeline throttle'

    def __init__(self, t0, win, targetRate, group, pipeline, search=None, requireManualRestart=False, conf=0.9):
        ### record data about the pipeline (equivalently, the lvalert node)
        self.group    = group
        self.pipeline = pipeline
        self.search   = search

        ### set self.graceid for easy lookup and automatic management
        self.graceid = "%s_%s"%(group, pipeline)
        if search:
            self.graceid = "%s_%s"%(self.graceid, search)

        self.description = "a throttle on the events approval processor will react to from %s_%s"%(group, self.graceid)

        tasks = [Throttle(win, targetRate, conf=conf, requireManualRestart=requireManualRestart) ### there is only one task!
                ]
        super(PipelineThrottle, self).__init__(t0, tasks) ### delegate to parent

    def add(self, graceid_data):
        '''
        adds a graceid to the ManagePipelineThrottleEvents task
        delegates to the task
        '''
        self.tasks[0].add( graceid_data ) ### only one task!

    def pop(self, ind=0):
        '''
        removes a graceid from the ManagePipelineThrottleEvents task and returns it
        delegates to the task
        '''
        return self.tasks[0].pop( ind ) ### only one task!

    def reset(self):
        '''
        reset the throttle
        delegates to the task
        '''
        self.tasks[0].reset()

    def isThrottled(self):
        '''
        determines if this pipeline is throttled
        delegates to the task
        '''
        return self.tasks[0].isThrottled()

    def execute(self, verbose=False):
        '''
        manage internal data, removing old events if necessary
        we overwrite the parent's method because we don't want to move the task to completedTasks after execution
        '''
        task = self.tasks[0] ### there is only one task!
        if task.hasExpired():
            task.execute( verbose=verbose )
        self.expiration = task.expiration

class Throttle(utils.Task):
    '''
    FILL ME IN

    the task associated with PipelineThrottle

    sets expiration to the oldes event in events + win
      when expired, we pop all evnets older than now-win and re-set expiration.
      if there are no events, we set expiration to infty so it doesn't get cleaned up

    note: using this Task to update something in PipelineThrottle is perhaps convoluted and stupid. Maybe Reed should re-think that design choice?
    '''
    name = 'throttle'
    description = 'a task that manages which events are tracked as part of the PipelineThrottle'

    def __init__(self, win, targetRate, conf=0.9, requireManualReset=False):
        self.win        = win ### the window over which we track events
        self.targetRate = targetRate ### the target rate at which we expect events
        self.conf       = conf ### determines the upper limit on the acceptable number of events in win via a poisson one-sided confidence interval

        self.computeNthr() ### compute the threshold number of events assuming a poisson process

        self.requireManualRestart = requireManualRestart

        self.events = [] ### list of data we're tracking
        super(Throttle, self).__init__(win, self.manageEvents) ### delegate to parent. Will call setExpiration, which we overwrite to manage things as we need here

    def computeNthr(self):
        '''
        determines the upper limit on the acceptable number of events within win based on targetRate and conf
        assumes triggers are poisson distributed in time

        finds the minimum Nthr such that
            \sum_{n=0}^{N} p(n|targetRate*win) >= conf
        via direct iteration.

        WARNING: this could be slow for large targetRate*win or large conf!
        '''
        ### handle special cases where algorithm won't converge
        if (self.conf>1) or (self.conf<0):
            raise ValueError('unphysical confidence level!')
        elif self.conf==1:
            self.Nthr = np.infty

        ### set up direct iteration
        k = self.targetRate*self.win
        self.Nthr = 0
        logProb = self.__logProb__(n, k)
        logConf = np.log(self.conf)

        ### integrate
        while logProb < logConf:
            self.Nthr += 1
            logProb = self.__sumLogs__( logProb, self.__logProb__(self.Nthr, k) )

    def __sumLogs__(self, *logs ):
        '''
        take the sum of logarithms to high precision
        '''
        logs = np.array(logs)
        maxLog = np.max(logs)
        return np.log( np.sum( np.exp( logs-maxLogs ) ) ) + maxLogs

    def __logProb__(self, n, k):
        '''
        return the logarithm of the poisson probability
        '''
        return n*np.log(k) - k - self.__logFactorial__(n)

    def __logFactorial__(self, n):
        '''
        return the log of a factorial, using Stirling's approximation if n >= 100
        '''
        if n < 100:
            return np.log( np.factorial(n) )
        else:
            return 0.5*np.log(np.pi*2*n) + n*np.log(n) - n

    def manageEvents(self):
        '''
        actually manage the events that are being tracked
        '''
        raise NotImplementedError('write ManagePipelineThrottleEvents.manageEvents')

    def add(self, graceid_data):
        '''
        adds a graceid to self.events and keeps them ordered
        '''
        raise NotImplementedError

    def pop(self, ind=0):
        '''
        removes a graceid from self.events and returns it
        '''
        raise NotImplementedError

    def reset(self):
        '''
        resets the throttle
        '''
        raise NotImplementedError

    def setExpiration(self, t0):
        '''
        sets expiration based on t0 and internal data (self.win and self.events)
        '''
        raise NotImplementedError

    def isThrottled(self):
        '''
        determines if we are throttled
        '''
        raise NotImplementedError

#-------------------------------------------------
# Grouper
# used to group nearby events 
#-------------------------------------------------

class Grouper(utils.QueueItem):
    '''
    FILL ME IN
    '''
    name = 'grouper'
    
    def __init__(self, t0, groupTag, nodes):
        ### record data bout this group
        self.groupTag = groupTag

        self.description = "a grouper object collecting events from nodes in (%s) and calling the result %s"%(", ".join(nodes), groupTag)

        tasks = [DefineGroup() ### only one task!
                ]
        super(Grouper, self).__init__(t0, tasks) ### delegate to parent

    def add(self, graceid_data):
        '''
        adds a graceid to the DefineGroup task
        delegates to the task
        '''
        self.tasks[0].add( graceid_data ) ### only one task!

class DefineGroup(utils.Task):
    '''
    Fill me in

    the taks associated with Grouper.
    '''
    name = 'define group'
    description = 'a task that defines a group and selects which element is preferred'

    def __init__(self, timeout):
        self.events = [] ### track the graceids that are associated with this group
        super(DefineGroup, self).__init__(timeout, self.decide) ### delegate to parent

    def add(self, graceid_data):
        '''
        adds graceid_data to internal group
        '''
        raise NotImplementedError

    def decide(self, verbose=False):
        '''
        decide which event is preferred and "create the group" in GraceDB
        '''
        raise NotImplementedError
