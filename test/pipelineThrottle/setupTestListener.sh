#! /bin/sh
#
#  setupTestListener.sh
#
#  Created by:    Min-A Cho
#  Creation date: June 8, 2017
#
#  Modified by:
#  Modified date:
#
#  Purpose: Script to download the latest version of lvalertMP and lvalertTest, and the specific git hash of approval_processorMP and save it to a directory specified by the user.
#

# Usage message.
usage="""setupTestListener.sh (v1.0)

Downloads the latest lvalertMP and lvalertTest repositories to a specified directory, downloads a specific git hash of approval_processorMP.

   --dir | -d  <PATH>         : Directory path to which to clone the downloaded LALSuite repository.
   --help | -h                : Print this help
"""

USERNAME=${USER}
HOME_DIR=/home/${USERNAME}

# Default script variables.
REPO_DIR="${HOME_DIR}"       # Default directory to which to clone the repositories.

# Get user arguments.
while [ -n "$1" ]
do
   case $1
      in
      --dir | -d) # Use the specified directory for the repository clone.
         REPO_DIR="${2}"
         shift; shift
         ;;
      --help | -h)   # Print the help.
         echo ${usage}
         shift
         ;;
      *) # Ignore anything else
         shift
         ;;
   esac
done

EMAIL=""
# Force the user to actually input an email address.
while [ -z "${EMAIL}" ]
do
   echo "You must enter an email address (ex.: albert.einstein@ligo.org): "
   read EMAIL
done

LIGO_NAME=""
# Force the user to actually input a LIGO ID. This is for sending lvalert commands later, to albert.einstein-test
while [ -z "${LIGO_NAME}" ]
do
   echo "You must enter a LIGO ID (ex.: albert.einstein) for sending commands to the albert.einstein-test lvalert node: "
   read LIGO_NAME
done


LVALERTMP_DIR="${REPO_DIR}/lvalertMP"
rm -rf ${LVALERTMP_DIR}
LVALERTTEST_DIR="${REPO_DIR}/lvalertTest"
rm -rf ${LVALERTTEST_DIR}
APPROVAL_PROCESSORMP_DIR="${REPO_DIR}/approval_processorMP"
rm -rf ${APPROVAL_PROCESSORMP_DIR}

# Proceed with the download process.
git clone "https://github.com/reedessick/lvalertMP.git" ${LVALERTMP_DIR}
git clone "https://github.com/deepchatterjeeligo/lvalertTest.git" ${LVALERTTEST_DIR}
git clone "https://github.com/mina19/approval_processorMP.git" ${APPROVAL_PROCESSORMP_DIR}
#git clone "https://github.com/deepchatterjeeligo/approval_processorMP.git" ${APPROVAL_PROCESSORMP_DIR}

echo "Checking out hash 3e123dd of lvalertMP, which is the version running on Grinch installation"
cd ${LVALERTMP_DIR}
git checkout 3e123dd

echo "Checking out branch testingPipelineThrottle in approval_processorMP"
cd ${APPROVAL_PROCESSORMP_DIR}
git checkout -b testingPipelineThrottle origin/testingPipelineThrottle

echo "Creating FAKDB_DIR, OUT_DIR, and COMMAND_FILE directories"
cd ${HOME_DIR}
FAKEDB_DIR=${APPROVAL_PROCESSORMP_DIR}/test/FAKE_DB            # store fake events
LVALERTOUTFILE=${FAKEDB_DIR}/lvalert.out  # store lvalerts received and sent

OUT_DIR=${APPROVAL_PROCESSORMP_DIR}/test/OUT_DIR               # store temporary files here
TMPFILE=${OUT_DIR}/tmpfile.out            # store lvalerts to be sent

COMMAND_DIR=${APPROVAL_PROCESSORMP_DIR}/test/COMMAND_FILE      # store commands received and sent
COMMANDSFILE=${COMMAND_DIR}/commands.txt  # commands file

mkdir -p ${FAKEDB_DIR}
mkdir -p ${OUT_DIR}
mkdir -p ${COMMAND_DIR}
echo "DONE"

echo "Clearing FAKE_DB, OUT_DIR, and COMMAND_FILE"
rm -rf ${FAKEDB_DIR}/*
rm -rf ${OUT_DIR}/*
rm -rf ${COMMAND_DIR}/*
echo "DONE"

echo "Creating new tmpfile.out, lvalert.out, and commands.txt files"
echo -n > ${LVALERTOUTFILE}
echo -n > ${TMPFILE}
echo -n > ${COMMANDSFILE}
echo "DONE"

echo "Creating approval_processorMP public files directory"
PUBLIC_DIR=${HOME_DIR}/public_html/monitor/approval_processorMPTest/files
mkdir -p ${PUBLIC_DIR}
rm -rf ${PUBLIC_DIR}

PUBLIC_LOGDIR=${PUBLIC_DIR}/log
mkdir -p ${PUBLIC_LOGDIR}
echo "DONE"

echo "Making approval_processorMP configuration files to point to FAKE_DB directory"
cd ${APPROVAL_PROCESSORMP_DIR}/etc
echo "[approval_processorMP]
nodes = cbc_mbtaonline cbc_gstlal_lowmass cbc_gstlal_highmass cbc_pycbc burst_cwb_allsky burst_lib ${LIGO_NAME}-test
childConfig = ${APPROVAL_PROCESSORMP_DIR}/etc/childConfig-approval_processorMPTest.ini
verbose = True
sleep = 0.1
maxComplete = 100
maxFrac = 0.5
recipients = ${EMAIL}" > lvalert_listenMP-approval_processorMPTest.ini

echo "[general]
; process_type is used to load libraries and determine behavior
process_type = approval_processorMP
; log_directory is where output, log, and error of running approval_processorMP instance is recorded
log_directory = ${PUBLIC_LOGDIR}/

; checks that are to be performed. we expect one section for each check listed here
checks = labelCheck, farCheck, injectionCheck, operator_signoffCheck, advocate_signoffCheck, iDQ_joint_fapCheck, have_lvem_skymapCheck

; approval_processorMP_logfile is the extension for the logger used by approval_processorMP to record its actions
approval_processorMP_logfile = /approval_processorMP.log
approval_processorO1_logfile = /approval_processor.log

; client is the gracedb api you want to use
client = ${FAKEDB_DIR}

; approval_processorMPfiles is the local file directory where the EventDicts.p, EventDicts.txt, and log file will be saved
; leave out the home directory location and end forward slash
approval_processorMPfiles = /public_html/monitor/approval_processorMPTest/files

voeventerror_email = ${EMAIL}

; forgetmenow_timeout is the time in seconds we should wait after last lvalert to delete an event dictionary
; currently set to 1 week = 604800
forgetmenow_timeout = 604800

; -------------- sending out VOEvents -------------------
; force_all_internal = 'yes' uses internal = 1 when calling client.CreateVOEvent. This means all VOEvents will be internal, meaning they will not be sent to astronomers. This flag should be set whenever testing.
; preliminary_internal is a list of pipelines for which we keep the Preliminary VOEvents internal
; if there is more than one pipeline in the list, separate with commas. for example, 'LIB, gstlal'
force_all_internal = yes
preliminary_internal = MBTAOnline, gstlal, pycbc, CWB, LIB

;-----------------------------------------------------------------------------
; GRB circulars
;-----------------------------------------------------------------------------
[GRB_alerts]
; em_coinc_text is the text template filled in by information from the RAVEN pipeline
em_coinc_text = A coincidence was found between a GRB trigger {0} from {1} and a gravitational-wave trigger {2}. The tentative False Alarm Rate of such a coincidence is {3}.
; coinc_text is the text template filled in by information from the online or offline X-pipeline or PyGRB pipelines
coinc_text = A coherent search of gravitational-wave data coincident with {0} produced a promising candidate. The tentative False Alarm Probability of such a coincidence is {1}.
; notification_text is the content of email sent to GRB enthusiasts when a coincidence is found and approval_processorMP uploads a json to event candidate page
notification_text = A json file was loaded into GraceDb by approval_processorMP. Please take a look online.
grb_email = ${EMAIL}

;-----------------------------------------------------------------------------
; basic checks for event
;-----------------------------------------------------------------------------
[labelCheck]
; checks for DQV or INJ label. we further have the option to treat hardware injections as real events or not using the 'hardware_inj' parameter

; --------------- hardware injections -------------------
; hardware_inj is either 'yes' or 'no'. 'yes' means treat hardware injection events as real events. 'no' means we do not.
; for engineering runs we sometimes treat hardware injections as real events so it is set to 'yes'. 
; for science runs it should say 'no'.
; wait_for_hardware_inj is the number of seconds to wait before querying gracedb for to see if INJ label has been applied for new triggers
hardware_inj = no
wait_for_hardware_inj = 10

[farCheck]
; checks whether the false alarm rate is lower than the 'default_farthresh' or pipeline specific 'farthresh' parameter
; ---------------- FAR ----------------------------------
; 3.17e-08 is one per year. this is the threshold set for post-O1 opportunistic running
; 3.8e-07 is one per month
; 1.9e-07 is one per two months
; 1.65e-06 is one per week
default_farthresh = 1.9e-07
;farthresh[gstlal.LowMass] = 1.9e-07
open_default_farthresh = -1
; open_default_farthresh is the far threshold to send open alerts (it is 3.17e-10 for 1 per 100 years)
;farthresh[gstlal.HighMass] = 1.9e-07
;farthresh[MBTAOnline.] = 1.9e-07

[injectionCheck]
; time_duation determines whether any hardware injections were found +/-'time_duration' seconds of the event gpstime
time_duration = 2

[operator_signoffCheck]
; checks that signoffs from each relevant instrument site is 'OK'. we have the option to wait for human signoffs or not using the 'humanscimons' parameter
; ---------------- operator signoffs --------------------
; humanscimons is either 'yes' or 'no'. 'yes' means we wait for human signoffs. 'no' means we do not.
humanscimons = yes

[advocate_signoffCheck]
; checks that EM follow-up advocates 'OK' the event. we have the option to wait for advocate signoffs or not using the 'advocates' parameter
; ---------------- advocates ----------------------------
; advocates is either 'yes' or 'no'. 'yes' means we wait for a follow-up advocate to signoff. 'no' means we do not.
; advocate_text is the 1-2 line alert that will be read aloud to advocates via a phone call using a voice synthesizer.
; advocate_email is set during observing runs to lvc-cloud-phone@email2phone.net
advocates = yes
advocate_text = A transient candidate passed the follow-up criteria. Please check your email immediately and alert others.
advocate_email = ${EMAIL}

[idq_joint_fapCheck]
; checks that the joint fap idq value is above the 'default_idqthresh' or pipeline specific 'idqthresh' parameter
; ---------------- idq ----------------------------------
; ignore_idq is a list of groups that will not use idq information.
; default_idqthresh is the value used for idq checks if pipeline and search are not specified with different thresholds
; all idq thresholds for a specific pipeline and search must be added in the form idqthresh[pipeline.search]
; list idq_pipelines we want to use separated by commas. for example, 'ovl, mvsc' means use both ovl and mvsc iDQ pipelines.
ignore_idq = CBC
;idqthresh[CWB.AllSky] = 0.01
default_idqthresh = 0.01
idq_pipelines = ovl

[have_lvem_skymapCheck]
; checks that skymap is tagged 'lvem' for sharing with EM follow-up partners
; ---------------- skymaps ------------------------------
; skymap_ignore_list is a list of skymap submitters to ignore separated by commas.
; for instance, it could say 'BWB Online at CIT, Cwb Analysis', etc.
skymap_ignore_list = BWB Online at CIT

;----------------- pipeline throttle --------------------
; for each possible group_pipeline_search or group_pipeline, set pipeline throttle parameters
; throttleWin is the time window over which we track events
; targetRate is the rate at which we expect events
; requireManualReset is 'True' or 'False'. if True, it requires an lvalertMP command to unthrottle the pipeline. if False the running instance will try to unthrottle the pipeline
; conf determines the upper limit on the acceptable number of events in the throttleWin via a poisson one-sided confidence interval

[default_PipelineThrottle]
throttleWin = 3600
targetRate = 1e-5
requireManualReset = False
conf = 0.9999

[CBC_MBTAOnline]
throttleWin = 3600
targetRate = 1e-4
requireManualReset = False
conf = 0.9999

[CBC_gstlal_HighMass]
throttleWin = 3600
targetRate = 1e-4
requireManualReset = False
conf = 0.9999

[CBC_pycbc_AllSky]
throttleWin = 3600
targetRate = 1e-5
requireManualReset = False
conf = 0.9999

[Burst_LIB_AllSky]
throttleWin = 3600
targetRate = 1e-5
requireManualReset = False
conf = 0.9999

[Burst_CWB_AllSky]
throttleWin = 3600
targetRate = 2.5e-6
requireManualReset = False
conf = 0.9999

[Burst_CWB_AllSkyLong]
throttleWin = 3600
targetRate = 2.5e-6
requireManualReset = False
conf = 0.9999

;----------------- grouper ------------------------------
; sets the window for grouping triggers together related to the same astrophysical event
[grouper]
; grouperWin determines the time window over which we group triggers from the time of the first ungrouped lvalertMP alert arrival
grouperWin = 3" > childConfig-approval_processorMPTest.ini

# There is an import error in lvalertTest_listenMP so fix that
# ligoMP.lvalert needs to change to lvalertMP.lvalert
cd ${LVALERTTEST_DIR}/bin
echo "${LVALERTTEST_DIR}/bin"
sed -i -e 's/ligoMP/lvalertMP/g' lvalertTest_listenMP 

# Comment out the line in approval_processorMPutils regarding sourcing comet
cd ${APPROVAL_PROCESSORMP_DIR}
sed -i -e 's/execfile/#execfile/g' approval_processorMPutils.py

# Record the repository directory so that we can simulate events more easily for testing purposes
cd ${APPROVAL_PROCESSORMP_DIR}/test/pipelineThrottle
echo "${REPO_DIR}" > repoDir.txt 

# Make the resetThrottleTest.sh command so that we can reset the CBC_gstlal_LowMass pipeline
echo "lvalertTest_commandMP --node=${LIGO_NAME}-test -f ${COMMANDSFILE} group,CBC pipeline,gstlal search,LowMass resetThrottle -v" > resetThrottleTest.sh

# Make it easier for sourcing paths and python paths for testing purposes
echo "export PYTHONPATH=${LVALERTTEST_DIR}/lib:${PYTHONPATH}
export PATH=${LVALERTTEST_DIR}/bin:${PATH}
export PYTHONPATH=${LVALERTMP_DIR}:${PYTHONPATH}
export PATH=${LVALERTMP_DIR}/bin:${PATH}
export PYTHONPATH=${APPROVAL_PROCESSORMP_DIR}:${PYTHONPATH}
export PATH=${APPROVAL_PROCESSORMP_DIR}/bin:${PATH}
export PYTHONPATH=${REPO_DIR}:${PYTHONPATH}" > setup.sh
chmod +x setup.sh

cd ${HOME_DIR}
echo "Adding configuration files and libraries to PATH and PYTHONPATH"
export PYTHONPATH=${LVALERTTEST_DIR}/lib:${PYTHONPATH}
export PATH=${LVALERTTEST_DIR}/bin:${PATH}
export PYTHONPATH=${LVALERTMP_DIR}:${PYTHONPATH}
export PATH=${LVALERTMP_DIR}/bin:${PATH}
export PYTHONPATH=${APPROVAL_PROCESSORMP_DIR}:${PYTHONPATH}
export PATH=${APPROVAL_PROCESSORMP_DIR}/bin:${PATH}
export PYTHONPATH=${REPO_DIR}:${PYTHONPATH}
echo "DONE"

echo "lvalertTest_listenMP -f ${FAKEDB_DIR} -c ${APPROVAL_PROCESSORMP_DIR}/etc/lvalert_listenMP-approval_processorMPTest.ini -C ${COMMANDSFILE} -v"

lvalertTest_listenMP -f ${FAKEDB_DIR} -c ${APPROVAL_PROCESSORMP_DIR}/etc/lvalert_listenMP-approval_processorMPTest.ini -C ${COMMANDSFILE} -v
