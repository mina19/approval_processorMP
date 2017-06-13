#!/bin/bash

# USAGE:: run_test.sh [FakeDb_directory] [Output directory] [/path/to/place/the/config/file/filename] 
FAKE_DB=$1		# Directory where events will be created
OUT_DIR=$2		# temporary directory to store upload files
CONFIG_FILE=$3		# config file of the event created, will be written by script
NUM_EVENTS=1		# number of this type of events to be created

# Event details
GROUP="CBC"
PIPELINE="gstlal"
SEARCH="LowMass"
INSTRUMENTS="H1,L1"
FAR=1e-8		# Event FAR
HUMANS=1		# Add humans section?
HUMAN_RESPONSE=1	# 0 for ADVNO, 1 for ADVOK
SEGDB2GRCDB=1		# Add segdb2grcdb section?
IDQ=1			# Add idq section?
IDQ_RESPONSE=1		# Pass/ fail criteria AP's IDQ threshold
SKYMAPS=0		# Adds various skymaps?
LVEM=1			# Add lvem tag?
EXT_TRIGGER=1		# Add ext-trigger section?
UNBLIND_INJ=1		# Add unblind-inj section?

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
	--idq=${IDQ} \
	--idq-response=${IDQ_RESPONSE} \
	--skymaps=${SKYMAPS} \
	--lvem=${LVEM} \
	--ext-trigger=${EXT_TRIGGER} \
	--unblind-inj=${UNBLIND_INJ}

echo "### Config written to ${CONFIG_FILE}"
echo "### Simulating fake event creation"

simulate.py \
	--num-events=${NUM_EVENTS} \
	--far=${FAR} \
	--gracedb-url=${FAKE_DB} \
	--instruments=${INSTRUMENTS} \
	--output-dir=${OUT_DIR} \
	-s \
	-v \
	${CONFIG_FILE}
