description = "a module that holds definitions of all required QueueItem and Task extensions used within approval processor"
author = "Min-A Cho (mina19@umd.edu), Reed Essick (reed.essick@ligo.org)"

#-------------------------------------------------

from eventDictClassMethods import *
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

    def setExpiration(self, t0):
        '''
        updates the expiration of all tasks as well as of the QueueItem itself.
        we overwrite the parent's function because we also touch the event_dict
        '''
        super(ForgetMeNow, self).setExpiration(t0) ### delegate to parent to touch tasks and self.expiration
                                                 ### if this throws an error, you need to update your version of lvalertMP

        ### why are we storing this? it is only called within this function and no one else needs it...
#        for task in self.tasks:
#            task.setExpiration(t0) ### update expiration of each task
#        self.sortTasks() ### sorting tasks in the QueueItem. This automatically updates self.expiration

        self.event_dicts[self.graceid].data['expirationtime'] = '{0} -- {1}'.format(self.expiration, convertTime(self.expiration)) ### records the expiration in local memory

class RemoveFromEventDicts(utils.Task):
    """
    first task that gets called by ForgetMeNow; it removes the graceID  event dictionary from eventDicts
    """
    name = 'removeEventDict'
    description = 'removes graceID event dictionary from self.event_dicts'

    def __init__(self, graceid, event_dicts, timeout, logger):
        self.graceid = graceid ### needed for lookup
        self.event_dicts = event_dicts ### pointer to the big "dictionary of dictionaries" which keeps local records of events' states
        self.logger = logger ### used to redirect print statements
        super(RemoveFromEventDicts, self).__init__(timeout, removeEventDict = self.removeEventDict) ### delegate to the parent class

    def removeEventDict(self, verbose=False, **kwargs):
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
    name = 'cleanUpQueue'
    description = 'cleans up queueByGraceID'

    def __init__(self, graceid, queue, queueByGraceID, timeout):
        self.graceid = graceid ### required for lookup
        self.queue = queue ### pointer for queue that is managed within interactiveQueue and passed to parseAlert
        self.queueByGraceID = queueByGraceID ### pointer to the queueByGraceID that is managed within interactiveQueue and passed to parseAlert
        super(CleanUpQueue, self).__init__(timeout, self.cleanUpQueue) ### delegate to parent class

    def cleanUpQueue(self, verbose=False, **kwargs):
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
# used to ignore certain pipelines when they submit too many events to GraceDb. 
# NOTE: this will not stop GraceDb from crashing but it will prevent approval processor from being overloaded
#-------------------------------------------------

def generate_ThrottleKey(group, pipeline, search=None):
    """
    computes the key assigned to self.graceid based on group, pipelin, and search
    encapsulated this way so we can call it elsewhere as well

    NOTE: we define this outside of the PipelineThrottle class because we need it without having access to an actual instance
    """
    if search:
        return "%s_%s_%s"%(group, pipeline, search)
    else:
        return "%s_%s"%(group, pipeline)

class PipelineThrottle(utils.QueueItem):
    '''
    A throttle that determines which events approval processor will actually track.
    This is implemented so that pipelines which are behaving badly do not trigger alerts.
    We delegate the task of updating the list of events upon expiration to this class's single task: Throttle(lvalerMPutils.Task)
    The decision making and applying labels, etc. is handled within *this* class. 
    In particular, .add() checks for state changes and applies labels as needed.

    assigns group_pipeline[_search] to self.graceid for easy lookup and management within queueByGraceID

    WARNING: all windowing is based off the time at which the alert is received by lvalert_listenMP rather than the gpstime or creation time. We may want to change this.
    '''
    name = 'pipeline throttle'

    def __init__(self, t0, win, targetRate, group, pipeline, search=None, requireManualReset=False, conf=0.9, graceDB_url='https://gracedb.ligo.org/api/'):
        ### record data about the pipeline (equivalently, the lvalert node)
        self.group    = group
        self.pipeline = pipeline
        self.search   = search

        ### set self.graceid for easy lookup and automatic management
        self.graceid = generate_ThrottleKey(group, pipeline, search)

        self.description = "a throttle on the events approval processor will react to from %s"%(self.graceid)

        self.events = [] ### list managed by Throttle task

        self.win        = win ### the window over which we track events
        self.targetRate = targetRate ### the target rate at which we expect events
        self.conf       = conf ### determines the upper limit on the acceptable number of events in win via a poisson one-sided confidence interval

        self.computeNthr() ### sets self.Nthr

        self.graceDB = GraceDb( graceDB_url )

        tasks = [Throttle(self.events, win, self.Nthr, requireManualReset=requireManualReset) ### there is only one task!
                ]
        super(PipelineThrottle, self).__init__(t0, tasks) ### delegate to parent

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
        logProb = self.__logProb__(self.Nthr, k)
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
        maxLogs = np.max(logs)
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
            return np.log( np.math.factorial(n) )
        else:
            return 0.5*np.log(np.pi*2*n) + n*np.log(n) - n

    def isThrottled(self):
        '''
        determines if this pipeline is throttled
        delegates to the task
        '''
        return self.tasks[0].isThrottled()

    def addEvent(self, graceid, t0):
        '''
        adds a graceid to self.events and keeps them ordered
        Checks for state changes of self.throttled and applies labels in GraceDb as necessary
        '''
        wasThrottled = self.isThrottled() ### figure out if we're already throttled before adding event
        for i, (_, t1) in enumerate(self.events): ### insert in order
            if t0 < t1:
                self.events.insert( i, (graceid, t0) )
                break
        else:
            self.events.append( (graceid, t0) )
        ### NOTE: we do not update expiration because it should be handled within a call to execute()
        ### either the expiration is too early, in which case execture() is smart enough to handle this
        ### (note, we expect events to come in in order, so we shouldn't ever have to set the expiration to earlier than it was before...)
        ### or expiration is already infty, in which case we require a manual reset anyway

        if wasThrottled: ### we are already throttled, so we just label the new graceid
            self.labelAsThrottled( graceid )
 
        elif self.isThrottled: ### we were not throttled, but now we are, so we label everything as throttled.
            for graceid, _ in self.events:
                self.labelAsThrottled( graceid )
 
        self.complete = False ### there is now at least one item being tracked
                              ### FIXME: need pointer to queue and queueByGraceID to update complete attribute

    def labelAsThrottled(self, graceid):
        """
        attempts to label the graceid as "EM_Throttled"
        """
        try:
            self.gdb.writeLabel( graceid, "EM_Throttled" )
        except:
            pass ### FIXME: print some intelligent error message here!

    def reset(self):
        '''
        resets the throttle (sets self.events = [])

        NOTE: when calling this, we should also call SortedQueue.resort() to ensure that SortedQueues remain sorted!
              this may be expensive, but should be rare!
              We can also play games with marking this as complete by hand, etc.
        An equivalent proceedure is to reset() is to remove the QueueItem from all SortedQueues. If a new event comes in, we will create a replacement
        '''
        self.events = []
        self.execute( verbose=False )

    def isThrottled(self):
        '''
        determines if this pipeline is throttled
        delegates to the task
        '''
        return self.tasks[0].isThrottled()

class Throttle(utils.Task):
    '''
    the task associated with PipelineThrottle

    sets expiration to the oldest event in events + win
      when expired, we pop all events older than now-win and re-set expiration.
      if there are no events, we set expiration to -infty and this will be cleaned up within PipelineThrottle (complete is set to True)
    '''
    name = 'manageEvents'
    description = 'a task that manages which events are tracked as part of the PipelineThrottle'

    def __init__(self, events, win, Nthr, requireManualReset=False):
        self.events = events ### list of data we're tracking. Should be a shared reference to an attribute of PipelineThrottle

        self.Nthr = Nthr

        self.requireManualReset = requireManualReset

        super(Throttle, self).__init__(win, self.manageEvents) ### delegate to parent. Will call setExpiration, which we overwrite to manage things as we need here
        #                               ^win is stored as timeout via delegation to Parent

    def isThrottled(self):
        '''
        return len(self.events) > self.Nthr
        '''
        return len(self.events) > self.Nthr

    def manageEvents(self, verbose=False, *args, **kwargs):
        '''
        actually manage the events that are being tracked
        this is called from execute() and will remove events from the known set
        the exception is if we are already throttled and we require manual reset. 
        Then we update expiration to infty and hold onto all events.
        '''
        ### if we are not already throttled and require manual reset, we forget about events that are old enough
        if not (self.isThrottled() and self.requireManualReset):
            t = time.time() - self.timeout ### cut off for what is "too old"
            while len(self.events):
                graceid, t0 = self.events.pop(0)
                if t0 > t: ### event is recent enough that we still care about it
                    self.events.insert(0, (graceid, t0) ) ### add it back in 
                    break

        ### determine how we set the expiration by how many events we have left
        if self.isThrottled() and self.requireManualReset: ### we don't expire because we don't forget old events
            self.setExpiration( np.infty )

        elif self.events: ### we do forget old events and there are events being tracked
            self.setExpiration( self.events[0][-1] )

        else: ### no events, set expiration so this goes away quickly
            self.setExpiration( -np.infty )

#-------------------------------------------------
# Grouper
# used to group nearby events 
#-------------------------------------------------

class Grouper(utils.QueueItem):
    '''
    A QueueItem which groups neighboring GraceDb entries together and makes automatic downselection to select a preferred event.
    This is supported to enforce The Collaboration's mandte that we will only release a single alert for each "physical event".

    WARNING: grouping is currently done by the time at which lvalert_listenMP recieves the alert rather than gpstime or creation time. We may want to revisit this.

    as currently implemented, the group stays "open" until t0+win=closure. 
    At this point, it begins trying to decide via delegations to it's task. 
    If it cannot decide immediately (eg: not enough DQ info is available), it will punt "wait" seconds and try again. 
    This polling will continue until we have enough info to decide or we reach a maximum timeout of "maxWait" after the window closes. 
    '''
    name = 'grouper'
    
    def __init__(self, t0, win, groupTag, eventDicts, wait=1, maxWait=60, graceDB_url='https://gracedb.ligo.org/api'):
        self.graceid = groupTag ### record data bout this group

        self.eventDicts = eventDicts ### pointer to the dictionary of dictionaries, which we will need to determine whether a decision can be made

        self.description = "a grouper object collecting events and calling the result %s"%(groupTag)

        self.events = [] ### shared reference that is passed to DefineGroup task

        self.t0 = t0
        self.closure = t0+win ### when the acceptance gate closes

        self.wait = wait ### the amount we wait (repeatedly) while looking for more information before making a decision
        self.maxWait = maxWait ### the maximum amount of time after self.closure that we wait for necessary info to make a decision

        tasks = [DefineGroup(self.events, eventDicts, win, graceDB_url=graceDB_url) ### only one task!
                ]
        super(Grouper, self).__init__(t0, tasks) ### delegate to parent

    def isOpen(self):
        '''
        determines whether the Group is still accepting new events
        '''
        return time.time() < self.closure

    def addEvent(self, graceid):
        '''
        adds a graceid to the DefineGroup task
        NOTE: we do NOT check whether the grouper is open before adding the event. 
        This allows us the flexibility to ignore which groupers are still open if needed and "force" events into the mix.
        '''
        self.events.append( graceid )

    def canDecide(self):
        """
        determines whether we have enough information to make this decision

        currently, we only require FAR and pipeline information, which we *know* we already have in eventDicts. 
        Thus, we return True without doing anything.
        
        We may want to do something like the following for more complicated logic:
            goodToGo = True
            for graceid in self.events: ### iterate through events in this group
                event_dict = self.eventDicts[graceid]
                goodToGo *= event_dict.has_key('far') ### ensure we have FAR information
                goodToGo *= event_dict.has_key('group') and event_dict.has_key('pipeline') and event_dict.has_key('search') ### ensure we have pipeline information
            return goodToGo
        """
        return True

    def execute(self, verbose=False ):
        '''
        override parent method to handle the case where we cannot make a decision yet
        we can just set this up to poll every second or so until we can decide or there is a hard timeout. Then we force a decision.
        '''
        if self.canDecide() or (time.time() > self.closure+self.maxWait): ### we can decide or we've timed out
            super(Grouper, self).execute( verbose=verbose ) ### delegate to the parent
        else: ### we have not timed out and we cannot yet decide
            self.setExpiration( self.t0+self.wait ) ### increment the expiration time by wait

class DefineGroup(utils.Task):
    '''
    the Task associated with Grouper. 
    When the Grouper object expires, this is called and will actually encapsulte the downselection logic.
    It also manages labeling in GraceDb, but does not modify local data structures. Instead, we expect those to be updated by the forthcoming alert_type="label" LVAlert messages.
    '''
    name = 'decide'
    description = 'a task that defines a group and selects which element is preferred'

    def __init__(self, events, eventDicts, timeout, graceDB_url='https://gracedb.ligo.org/api'):
        self.events = events ### shared reference to events tracked within Grouper QueueItem
        self.eventDicts = eventDicts ### shared reference pointing to the local data about events
        self.graceDB = GraceDb( graceDB_url )
        super(DefineGroup, self).__init__(timeout, self.decide) ### delegate to parent

    def decide(self, verbose=False):
        '''
        decide which event is preferred and "create the group" in GraceDb

        the actual decision making process is delegated to self.choose, which compares pairs of graceid's and picks one it prefers

        NOTE: labeling of events occurs here (either 'Selected' or 'Superseded'
              we also must know how to make decisions with incomplete information
              As we make decisions based on more complicated logic requiring more information, we'll also need to update Grouper.canDecide() to reflect this.
        '''
        selected = self.events[0] ### we assume there is at least one event...
        superceded = []
        ### iterate through remaining events and decide if we like any of them better than selected
        for graceid in self.events[1:]:

            if selected == self.choose( selected, graceid ): ### we reject graceid
                supreceded.append( graceid )
            else: ### we reject the old selected and now prefer the new graceid
                superceded.append( selected )
                selected = graceid

        ### label events in GraceDb. This will initiate all the necessary processing when alert_type='label' messages are received
        self.labelAsSelected( selected )
        for graceid in superceded:
            self.labelAsSuperseded( graceid )

    def choose(self, graceidA, graceidB ):
        """
        encapsulates logic that determines which event is preferred between a pair of events
        If we can rank all pairs of events in this way, we can immediately select an overall winner by iteration (ie: what's done in self.decide)

        CBC events are preferred above Burst events (regardless of FAR)
        After downselecting based on group, event with the lowest FAR is preferred.
        Do we want to downselect based on anything else? 

        THIS CAN BECOME VERY COMPLICATED VERY QUICKLY.

        returns the preferred graceid
        """
        event_dictA = self.eventDicts[graceidA]
        event_dictB = self.eventDicts[graceidB]

        ### choose based on group_pipeline_search using the class that does this
        groupPipelineSearchA = GroupPipelineSearch(event_dictA['group'], event_dictA['pipeline'], event_dictA['search'])
        groupPipelineSearchB = GroupPipelineSearch(event_dictB['group'], event_dictB['pipeline'], event_dictB['search'])
        if groupPipelineSearchA != groupPipelineSearchB: ### we can make a decision based on this!
            if groupPipelineSearchA > groupPipelineSearchB:
                return graceidA
            else:
                return graceidB

        ### choose based on FAR
        farA = event_dictA['far']
        farB = event_dictB['far']
        if farA != farB: ### we can make a decision based on this!
            if farA < farB:
                return graceidA ### prefer the smaller far
            else:
                return graceidB 

        ### at this point, we have two events with identical GroupPipelineSearch ranks and identical FARs
        ### these should be "indistinguishable" so we pick the first of the two arguments
        ### this is an arbitrary choice, but we need to make it.
        return graceidA

    def labelAsSelected(self, graceid):
        """
        attempts to label the graceid as "Selected"
        """
        try:
            self.gdb.writeLable( graceid, "Selected" )
        except:
            pass ### FIXME: print some intelligent error message here!

    def labelAsSuperseded(self, graceid):
        """
        attempts to label the graceid as "Superseded"
        """
        try:
            self.gdb.writeLable( graceid, "Superseded" )
        except:
            pass ### FIXME: print some intelligent error message here!

class GroupPipelineSearch():
    '''
    a simple wrapper for the group_pipeline_search combinations that knows how to compare them and find a preference

    this is done by mapping group, pipeline, search combinations into integers and then comparing the integers

    NOTE: bigger things are more preferred and the relative ranking is hard coded into immutable attributes of this class
          comparison is done first by group. If that is inconclusive, we then compare pipelines. If that is inconclusive, we then check search.
    
    we prefer:
        cbc over burst
        no pipeline is prefered
        events with 'search' specified are preferred over events without 'search' specified

    WARNING: if we do not know about a pariticular group, pipeline, or search, we assign a rank of -infty because we don't know about this type of event
    '''
    ### dictionaries that map group, pipeline, search into 
    __groupRank__    = {'cbc'  :1, ### cbc events are preferred over burst
                        'burst':0,
                       }
    __pipelineRank__ = {'gstlal'      :0, ### all pipelines are equal
                        'mbtaonline'  :0,
                        'pycbc'       :0,
                        'gstlal-spiir':0,
                        'cwb'         :0,
                        'lib'         :0,
                       } ### all pipelines are equal
    __searchRank__   = {'lowmass' :1,   ### events with "search" specified are preferred over events without "search" specified
                        'highmass':1,
                        'allsky'  :1,
                        ''        :0,
                        None      :0,
                       }

    def __init__(self, group, pipeline, search=None):
        self.group = group
        if self.__groupRank__.has_key(group):
            self.groupRank = self.__groupRank__[group]
        else:
            self.groupRank = -1

        self.pipeline = pipeline
        if self.__pipelineRank__.has_key(pipeline):
            self.pipelineRank = self.__pipelineRank__[pipeline]
        else:
            self.pipelineRank = -1

        self.search = search
        if self.__searchRank__.has_key(search):
            self.searchRank = self.__searchRank__[search]
        else:
            self.searchRank = -1

    def __str__(self):
        return "%s, %s, %s : %d, %d, %d"%(self.group, self.pipeline, self.search, self.groupRank, self.pipelineRank, self.searchRank)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return (self.groupRank==other.groupRank) and (self.pipelineRank==other.pipelineRank) and (self.searchRank==other.searchRank)

    def __neq__(self, other):
        return (not self==other)

    def __lt__(self, other):
        if self.groupRank == other.groupRank: ### we must decide based on pipelineRank
            if self.pipelineRank == other.pipelineRank: ### we must decide based on searchRank
                return self.searchRank < other.searchRank ### decide based on searchRank

            else: ### we can decide based on pipelinerank
                return self.pipelineRank < other.pipelineRank

        else: ### we can decide based on group alone
            return self.groupRank < other.groupRank

    def __gt__(self, other):
        if self.groupRank == other.groupRank: ### we must decide based on pipelineRank
            if self.pipelineRank == other.pipelineRank: ### we must decide based on searchRank
                return self.searchRank > other.searchRank ### decide based on searchRank

            else: ### we can decide based on pipelinerank
                return self.pipelineRank > other.pipelineRank

        else: ### we can decide based on group alone
            return self.groupRank > other.groupRank

    def __ge__(self, other):
        return (not self < other)

    def __le__(self, other):
        return (not self > other)
