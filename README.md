# approval_processorMP
approval_processorMP is software developed to validate/check low-latency gravitational wave triggers.

the MP stands for multi-processing meaning there is only one running instance of the program ever, where the body of the code: approval_processorMPutils.parseAlert contains the bulk of the logic that runs checks on triggers.

it works off of the lvalertMP architecture and imports packages from that repository.

things to be done still with approval_processorMP:

1. grouper functionality
    grouper is a feature that automatically selects the best gravitational wave trigger to follow-up on for multi-messenger astronomy
