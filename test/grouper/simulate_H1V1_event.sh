#!/bin/bash

REPO_DIR=$(cat repoDir.txt)

# USAGE:: ./one_fake_gstlal.sh
FAKE_DB=${REPO_DIR}/approval_processorMP/test/FAKE_DB          # Directory where events will be created
OUT_DIR=${REPO_DIR}/approval_processorMP/test/OUT_DIR          # temporary directory to store upload files
CONFIG_FILE=${REPO_DIR}/approval_processorMP/test/virgoImplementation/gstlal.ini_1             # config file of the event created, will be written by script
NUM_EVENTS=1 # we are creating five events for testing grouper -- 2 cwb events and 3 gstlal events
EVENT_RATE=10000 # the rate for simulating events specified in Hz
INSTRUMENTS="H1,V1"
GPSTIME=0 # this will be edited when we call this script with tconvert now

${REPO_DIR}/lvalertTest/bin/simulate.py \
        --num-events=${NUM_EVENTS} \
        #--far=${FAR} \
        --gracedb-url=${FAKE_DB} \
        --instruments=${INSTRUMENTS} \
        --output-dir=${OUT_DIR} \
        --event-rate=${EVENT_RATE} \
        -s \
        -v \
        gstlal.ini_2 \
        --start-time=${GPSTIME} 
