#!/usr/bin/env python

description = "a module containing checks and parsing logic for approval_processorMP"
author = "Min-A Cho mina19@umd.edu"

#----------------------------------------------------------
# Import packages -----------------------------------------
#----------------------------------------------------------
#from ligo.lvalert import lvalertMPutils as utils

import os
import json
from sys import stdin
from ligo.gracedb.rest import GraceDb, HTTPError
import re
import urllib

import approval_processorMPutils as approval_utils

#--------------------------------------------------------------------------
# Tasks when current_state of event is new_to_preliminary
#--------------------------------------------------------------------------
new_to_preliminary = [
    'farCheck',
    'labelCheck',
    'injectionCheck'
    ]

#--------------------------------------------------------------------------
# Tasks when current_state of event is preliminary_to_initial
#--------------------------------------------------------------------------
preliminary_to_initial = [
    'farCheck',
    'labelCheck',
    'have_lvem_skymapCheck'
    'idq_joint_fapCheck'
    ]
if humanscimons=='yes':
    preliminary_to_initial.append('operator_signoffCheck')
if advocates=='yes':
    preliminary_to_initial.append('advocate_signoffCheck')

#--------------------------------------------------------------------------
# Tasks when current_state of event is initial_to_update
#--------------------------------------------------------------------------
initial_to_update = [
    'farCheck',
    'labelCheck',
    'have_lvem_skymapCheck'
    ]
