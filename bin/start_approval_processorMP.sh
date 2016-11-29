#!/bin/bash

thisDir=${PWD}

### lvalert_listenMP version of approval_processorMP
gdb_processor-approval_processorMP start \
    --bin    /home/gracedb.processor/opt/bin/ \
    --config /home/gracedb.processor/opt/etc/lvalert_listenMP-approval_processorMP.ini\
    --out    /home/gracedb.processor/public_html/monitor/approval_processorMP/files\

cd /home/gracedb.processor/public_html/monitor/approval_processorMP/files
ln -s /home/gracedb.processor/opt/etc/lvalert_listenMP-approval_processorMP.ini lvalert_listenMP-approval_processorMP.ini
ln -s /home/gracedb.processor/opt/etc/childConfig-approval_processorMP.ini childConfig-approval_processorMP.ini

### restarting things while approval_processorMP is running from lvalert-dev
#cd /home/gracedb.processor/lvalert-dev
#source setup.sh

#cd /home/gracedb.processor/lvalert-dev/approval_processorMP/bin
#start_comet

#cd /home/gracedb.processor/public_html/monitor/approval_processorMP/files
#ln -s /home/gracedb.processor/lvalert-dev/approval_processorMP/etc/lvalert_listenMP.ini lvalert_listenMP.ini
#ln -s /home/gracedb.processor/lvalert-dev/approval_processorMP/etc/childConfig-approval_processorMP.ini childConfig-approval_processorMP.ini
#cp -p stdout_stderr.log stdout_stderr.log_`date +%y-%m-%d_%H:%M`
#cd /home/gracedb.processor/lvalert-dev/approval_processorMP/bin
#./lvalert-init_approval_processorMP > /home/gracedb.processor/public_html/monitor/approval_processorMP/files/stdout_stderr.log 2>&1 &

cd ${thisDir}
