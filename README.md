# approval_processorMP
approval_processorMP is software developed to validate/check low-latency gravitational wave triggers.

the MP stands for multi-processing meaning there is only one running instance of the program ever, where the body of the code: approval_processorMPutils.parseAlert contains the bulk of the logic that runs checks on triggers.

it works off of the lvalertMP architecture and imports packages from that repository.

things to be done still with approval_processorMP:
1. lvalertMP command for unthrottling throttled pipelines
    a) need to write the extension to lvalertMP's commands.py
    b) it needs to load the queueByGraceID and queue
    c) delete the throttled pipeline's throttle key (group, pipeline, search) tuple
    d) look up references to the pipeline throttle queueItem from queueByGraceID and mark it as complete and THEN delete it

2. grouper functionality
    grouper is a feature that automatically selects the best gravitational wave trigger to follow-up on for multi-messenger astronomy
