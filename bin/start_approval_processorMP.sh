#!/bin/bash

thisDir=${PWD}

cd /home/gracedb.processor/lvalert-dev
source setup.sh

cd /home/gracedb.processor/public_html/monitor/approval_processorMP/files
cp /home/gracedb.processor/lvalert-dev/approval_processorMP/etc/lvalert_listenMP.ini lvalert_listenMP.ini
cp /home/gracedb.processor/lvalert-dev/approval_processorMP/etc/childConfig-approval_processorMP.ini childConfig-approval_processorMP.ini

cd /home/gracedb.processor/lvalert-dev/approval_processorMP/bin
./lvalert-init_approval_processorMP > /home/gracedb.processor/public_html/monitor/approval_processorMP/files/stdout_stderr.log 2>&1 &

cd ${thisDir}
