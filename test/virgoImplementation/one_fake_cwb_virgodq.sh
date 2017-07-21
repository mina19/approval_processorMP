#!/bin/bash

REPO_DIR=$(cat repoDir.txt)

# USAGE:: ./one_fake_gstlal.sh
FAKE_DB=${REPO_DIR}/approval_processorMP/test/FAKE_DB          # Directory where events will be created
OUT_DIR=${REPO_DIR}/approval_processorMP/test/OUT_DIR          # temporary directory to store upload files
CONFIG_FILE=${REPO_DIR}/approval_processorMP/test/virgoImplementation/cwb.ini_1             # config file of the event created, will be written by script
NUM_EVENTS=1

# Event details
GROUP="Burst"
PIPELINE="CWB"
SEARCH="AllSky"
INSTRUMENTS="H1,L1,V1"
FAR=1e-8		# Event FAR
HUMANS=1		# Add humans section?
HUMAN_RESPONSE=1	# 0 for ADVNO, 1 for ADVOK
SEGDB2GRCDB=0		# Add segdb2grcdb section?
VIRGODQ=1		# Add VirgoDQ section?
VIRGODQRESPONSE=1	# 0 for IS vetoed (fail); 1 for IS NOT vetoed (pass)
VIRGOINJ=0		# 0 for DID NOT FIND injections; 1 for DID FIND injections
IDQ=1			# Add idq section?
IDQ_RESPONSE=1		# Pass/ fail criteria AP's IDQ threshold
SKYMAPS=1		# Adds various skymaps?
LVEM=1			# Add lvem tag?
EXT_TRIGGER=0		# Add ext-trigger section?
UNBLIND_INJ=0		# Add unblind-inj section?

if [ ! -d ${FAKE_DB} ];then
	mkdir -p ${FAKE_DB}
fi

if [ ! -d ${OUT_DIR} ];then
	mkdir -p ${OUT_DIR}
fi

if [ ! -d $(dirname ${CONFIG_FILE}) ];then
	mkdir -p $(dirname ${CONFIG_FILE})
fi

if [ ! -f ${CONFIG_FILE} ];then
	touch ${CONFIG_FILE}
fi

# Write the config file
echo "### Writing config file"
./build_testing_config \
	--file=${CONFIG_FILE} \
	--group=${GROUP} \
	--pipeline=${PIPELINE} \
	--search=${SEARCH} \
	--instruments=${INSTRUMENTS} \
	--humans=${HUMANS} \
	--human-response=${HUMAN_RESPONSE} \
	--segdb2grcdb=${SEGDB2GRCDB} \
	--virgodq=${VIRGODQ} \
	--virgodq-veto=${VIRGODQRESPONSE} \
	--virgo-inj=${VIRGOINJ} \
	--idq=${IDQ} \
	--idq-response=${IDQ_RESPONSE} \
	--skymaps=${SKYMAPS} \
	--lvem=${LVEM} \
	--ext-trigger=${EXT_TRIGGER} \
	--unblind-inj=${UNBLIND_INJ}

echo "### Config written to ${CONFIG_FILE}"
echo "### Simulating fake event creation"

${REPO_DIR}/lvalertTest/bin/simulate.py \
	--num-events=${NUM_EVENTS} \
	--far=${FAR} \
	--gracedb-url=${FAKE_DB} \
	--instruments=${INSTRUMENTS} \
	--output-dir=${OUT_DIR} \
	-s \
	-v \
	${CONFIG_FILE}
