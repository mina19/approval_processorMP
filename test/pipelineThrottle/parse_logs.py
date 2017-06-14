#!/usr/bin/python
from time import time, sleep
import re, os
from argparse import ArgumentParser
from ligoTest.lvalert import lvalertTestUtils as lvutils

parser = ArgumentParser(description= \
	"Parses log file continually to track log messages")
parser.add_argument('-f', '--log-file', required=True, help='Test log file you want to monitor')
parser.add_argument('-o', '--out-file', required=True,default='', help=\
						'The output file where test results are written')
parser.add_argument('-T', '--total-time',type=int,default=600,help=\
						'Total time test is expected to last')
parser.add_argument('-l', '--label', default='', help=\
						'Any label that you expect in the log file')
parser.add_argument('-m', '--message', default='', help=\
						'Any message that you expect in the log file')

args = parser.parse_args()
log_file = lvutils.FileMonitor(args.log_file)	# Monitor the log file
os.system('echo -n > '+args.out_file)		# Empty the output file (or create it)
os.system('echo Files will be monitored for %d seconds'%args.total_time+' >> '+args.out_file)
os.system('echo Monitoring '+args.log_file+' >> '+args.out_file)

start_time = time()
net_out=''
while time() <= (start_time + args.total_time):
	data = log_file.extract()
	# extract() returns a list of strings
	for line in data:
		message	= line[0]
		gid_pat	= re.compile("[GgTtMm]\d{6}")
		label_pat= re.compile('('+args.label+')'+'[\s\t]+label', re.IGNORECASE)
		msg_pat	= re.compile(args.message, re.IGNORECASE)
		graceid	= re.search(gid_pat, message).group() if re.search(gid_pat, message) else ''
		label	= re.search(label_pat, message).group(1) if re.search(label_pat, message) else ''
		msg	= re.search(msg_pat, message).group() if re.search(msg_pat, message) else ''
		
		out = ''
		if label or msg:
			out += "Found graceid  %s  "%(graceid,)
			out += "With label  %s  "%(label,) if label else ''
			out += "With message  %s  "%(msg,) if msg else ''
			out += "\n%s"%(message,) if label or msg else ''
		
		if out:
			f = open(args.out_file,'a')
			print >> f, out
			f.close()
		net_out+=out	
	# check file every 1 second
	sleep(1)
if not net_out:
	fail_msg = "Did not find label: %s or message: %s during the test"%(args.label,args.message)
	os.system("echo "+fail_msg+" >> "+args.out_file)	
