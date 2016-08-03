description = "a module that holds definitions of all required QueueItem and Task extensions used within approval processor"
author = "Min-A Cho (mina19@umd.edu), Reed Essick (reed.essick@ligo.org)"

#-------------------------------------------------

from ligoMP.lvalert import lvalertMPutils as utils
from ligo.gracedb.rest import GraceDb

import time

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
    description = 'upon execution delegates to RemoveFromEventDicts and CleanUpQueue in order to remove graceID from eventDicts and any assoicated queue items'

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
        super(ForgetMeNow, self).setExpiration() ### delegate to parent to touch tasks and self.expiration
                                                 ### if this throws an error, you need to update your version of lvalertMP

        ### why are we storing this? it is only called within this function and no one else needs it...
        self.convertTime = convertTime ### FIXME: this is not great and is caused by poor organization. 
                                       ### Functions like this that are needed in multiple modules and which have essentially no dependences should be defined in little modules that everyone can import
                                       ### rather than passed as arguments. This essentially means that only approval_processorMPutils can use this item. Although that's the expected use case, we shouldn't
                                       ### contrive the code such that this *must* be the case.
#        for task in self.tasks:
#            task.setExpiration(t0) ### update expiration of each task
#        self.sortTasks() ### sorting tasks in the QueueItem. This automatically updates self.expiration

        self.event_dicts[self.graceid]['expirationtime'] = '{0} -- {1}'.format(self.expiration, convertTime(self.expiration)) ### records the expiration in local memory

class RemoveFromEventDicts(utils.Task):
    """
    first task that gets called by ForgetMeNow; it removes the graceID  event dictionary from eventDicts
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
        ### FIXME: how will this know what convertTime() is? It isn't defined and it isn't passed in
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
    We delegate the task of updating the list of events upon expiration to this class's single task: Throttle(lvalerMPutils.Task)
    The decision making and applying labels, etc. is handled within *this* class. 
    In particular, .add() checks for state changes and applies labels as needed.

    assigns group_pipeline[_search] to self.graceid for easy lookup and management within queueByGraceID
    '''
    name = 'pipeline throttle'

    def __init__(self, t0, win, targetRate, group, pipeline, search=None, requireManualRestart=False, conf=0.9, graceDB_url='https://gracedb.ligo.org/api/'):
        ### record data about the pipeline (equivalently, the lvalert node)
        self.group    = group
        self.pipeline = pipeline
        self.search   = search

        ### set self.graceid for easy lookup and automatic management
        self.graceid = self.generate_key(group, pipeline, search)

        self.description = "a throttle on the events approval processor will react to from %s_%s"%(group, self.graceid)

        self.events = [] ### list managed by Throttle task

        self.win        = win ### the window over which we track events
        self.targetRate = targetRate ### the target rate at which we expect events
        self.conf       = conf ### determines the upper limit on the acceptable number of events in win via a poisson one-sided confidence interval

        self.computeNthr()

        self.throttled = False

        self.graceDB = GraceDB( graceDB_url )

        tasks = [Throttle(events, win, requireManualRestart=requireManualRestart) ### there is only one task!
                ]
        super(PipelineThrottle, self).__init__(t0, tasks) ### delegate to parent

    def generate_key(group, pipeline, search=None):
        """
        computes the key assigned to self.graceid based on group, pipelin, and search
        encapsulated this way so we can call it elsewhere as well
        """
        key = "throttle-%s_%s"%(group, pipeline)
        if search:
            key = "%s_%s"%(key, search)
        return key

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

    def add(self, graceid, t0):
        '''
        adds a graceid to self.events and keeps them ordered
        Checks for state changes of self.throttled and applies labels in GraceDB as necessary
        '''
        for i, (_, t1) in enumerate(self.events): ### insert in order
            if t0 < t1:
                self.events.insert( i, (graceid, t0) )
                break
        else:
            self.events.append( (graceid, t0) )

        throttled = len(self.events) > self.Nthr
        if throttled and self.throttled: ### we are already throttled, so we just label the new graceid
            self.labelAsThrottled( graceid )
 
        elif throttled: ### we were not throttled, but now we are, so we label everything as throttled.
            for graceid, _ in self.events:
                self.labelAsThrottled( graceid )
 
        self.throttled = throttled

    def labelAsThrottled(self, graceid):
        """
        attempts to label the graceid as "Throttled"
        """
        try:
            self.gdb.writeLable( graceid, "Throttled" )
        except:
            pass ### FIXME: print some intelligent error message here!

    def pop(self, ind=0):
        '''
        removes a graceid from self.events and returns it
        '''
        data = self.events.pop( ind )
        self.throttled = len(self.events) > self.Nthr
        return data

    def reset(self):
        '''
        resets the throttle (sets self.events = [])
        '''
        self.events = []
        self.throttled = False

    def isThrottled(self):
        '''
        determines if this pipeline is throttled
        delegates to the task
        '''
        return self.throttled

    def execute(self, verbose=False):
        '''
        manage internal data, removing old events if necessary
        we overwrite the parent's method because we don't want to move the task to completedTasks after execution unless there are no more events to be tracked
        '''
        task = self.tasks[0] ### there is only one task!
        if task.hasExpired():
            task.execute( verbose=verbose )
        self.expiration = task.expiration ### update expiration
        self.complete = len(events)==0 ### complete only if there are no more events being tracked

class Throttle(utils.Task):
    '''
    the task associated with PipelineThrottle

    sets expiration to the oldest event in events + win
      when expired, we pop all events older than now-win and re-set expiration.
      if there are no events, we set expiration to -infty and this will be cleaned up within PipelineThrottle (complete is set to True)
    '''
    name = 'throttle'
    description = 'a task that manages which events are tracked as part of the PipelineThrottle'

    def __init__(self, events, win, requireManualReset=False):
        self.events = events ### list of data we're tracking. Should be a shared reference to an attribute of PipelineThrottle

        self.computeNthr() ### compute the threshold number of events assuming a poisson process

        self.requireManualRestart = requireManualRestart

        super(Throttle, self).__init__(win, self.manageEvents) ### delegate to parent. Will call setExpiration, which we overwrite to manage things as we need here

    def manageEvents(self):
        '''
        actually manage the events that are being tracked
        this is called from execute() and will remove events from the known set
        the exception is if we are already throttled and we require manual reset. 
        Then we update expiration to infty and hold onto all events.
        '''
        ### if we are not already throttled and require manual reset, we forget about events that are old enough
        if not (self.isThrottled() and self.requireManualReset):
            t = time.time() - self.win ### cut off for what is "too old"
            while len(self.events):
                graceid, t0 = self.events.pop(0)
                if t0 > t: ### event is recent enough that we still care about it
                    self.events.insert(0, (graceid, t0) ) ### add it back in 
                    break
        self.setExpiration()

    def setExpiration(self, t0):
        '''
        sets expiration based on t0 and internal data (self.win and self.events)
        '''
        if self.isThrottled() and self.requireManualReset: ### we don't expire because we don't forget old events
            self.expiration = np.infty

        elif self.events: ### we do forget old events and there are events being tracked
            self.expiration = self.events[0][-1] + self.win

        else: ### no events, set expiration so this goes away quickly
            self.expiration = -np.infty

#-------------------------------------------------
# Grouper
# used to group nearby events 
#-------------------------------------------------

class Grouper(utils.QueueItem):
    '''
    A QueueItem which groups neighboring GraceDb entries together and makes automatic downselection to select a preferred event.
    This is supported to enforce The Collaboration's mandte that we will only release a single alert for each "physical event".
    '''
    name = 'grouper'
    
    def __init__(self, t0, win, groupTag, eventDicts):
        self.graceid = groupTag ### record data bout this group

        self.eventDicts = eventDicts ### pointer to the dictionary of dictionaries, which we will need to determine whether a decision can be made

        self.description = "a grouper object collecting events and calling the result %s"%(groupTag)

        self.events = [] ### shared reference that is passed to DefineGroup task

        tasks = [DefineGroup(self.events, win) ### only one task!
                ]
        super(Grouper, self).__init__(t0, tasks) ### delegate to parent

    def add(self, graceid):
        '''
        adds a graceid to the DefineGroup task
        '''
        self.events.append( graceid )

class DefineGroup(utils.Task):
    '''
    the Task associated with Grouper. 
    When the Grouper object expires, this is called and will actually encapsulte the downselection logic.
    It also manages labeling in GraceDb, but does not modify local data structures. Instead, we expect those to be updated by the forthcoming alert_type="label" LVAlert messages.
    '''
    name = 'define group'
    description = 'a task that defines a group and selects which element is preferred'

    def __init__(self, events, timeout):
        self.events = events ### shared reference to events tracked within Grouper QueueItem
        super(DefineGroup, self).__init__(timeout, self.decide) ### delegate to parent

    def canDecide(self):
        """
        determines whether we have enough information to make this decision
        """
        raise NotImplementedError('we need something like a "canDecide" method, but I\'m not sure this is the best place for it to live. Perhaps it should be a method of Grouper itself? It also isn\'t clear exactly how this would be called. Maybe we overwrite Grouper.execute() to handle this and play with expiration dates as necessary?')

    def decide(self, verbose=False):
        '''
        decide which event is preferred and "create the group" in GraceDB

        CBC events are preferred above Burst events (regardless of FAR estimates?)
        After downselecting based on group, event with the lowest FAR is preferred.
        Do we want to downselect based on anything else? THIS CAN BECOME VERY COMPLICATED VERY QUICKLY.
        '''
        raise NotImplementedError("write logic for event downselection here!")
