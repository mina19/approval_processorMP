#!/usr/bin/env bash

from eventDictClassMethods import *

config = loadConfig('yes')
client = config.get('general','client')
g = GraceDb(client)
graceid = 'G248769'

logger = loadLogger(config)
EM_Bright = {}
EM_Bright['ProbHasNS'] = 0.6
EM_Bright['ProbHasRemnant'] = 0.4
event_dict = createTestEventDict(graceid)
event_dict['em_bright_info'] = EM_Bright
event_dict['lvemskymaps']['1-skyprobcc_CWB.fits'] = 'Min-A Cho'
process_alert(event_dict, 'preliminary', g, config, logger)
