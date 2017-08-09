#!/bin/bash

# restore original github simulate_H1L1_events.sh, simulate_H1V1_event.sh, and simulate_H1L1V1_events.sh scripts
git checkout testingGrouper -- simulate_H1L1_events.sh
git checkout testingGrouper -- simulate_H1V1_event.sh
git checkout testingGrouper -- simulate_H1L1V1_events.sh

# call the scripts that create the config files
./one_fake_cwb_double.sh
./one_fake_cwb_virgodq.sh
./one_fake_gstlal_double.sh
./one_fake_gstlal_double_V1.sh
./one_fake_gstlal_triple.sh

GPSTIME="`tconvert now`"
echo $GPSTIME

# prompt the user for which type of grouper test to run
echo "Which grouper test do you wish to run? (options: R for regular, L for late trigger, and M for more than one grouper)"
read TESTTYPE

if [ $TESTTYPE = 'R' ]; then
    echo "Performing Regular grouper test -- simulating all events now"
    # fixing the simulate.py calling scripts to have the similar gpstimes so that the simulated events have similar gpstimes
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1L1_events.sh
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1V1_event.sh
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1L1V1_events.sh
    ./simulate_H1L1_events.sh
    ./simulate_H1L1V1_events.sh
    ./simulate_H1V1_event.sh

elif [ $TESTTYPE = 'L' ]; then
    echo "Performing Late grouper test -- will send H1V1 event more than 60 seconds after the other triggers to make sure the late trigger is sent after the decisionWin time has passed"
# fixing the simulate.py calling scripts to have the similar gpstimes so that the simulated events have similar gpstimes
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1L1_events.sh
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1V1_event.sh
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1L1V1_events.sh
    ./simulate_H1L1_events.sh
    ./simulate_H1L1V1_events.sh
    sleep 90
    ./simulate_H1V1_event.sh

elif [ $TESTTYPE = 'M' ]; then
    echo "Performing More than one grouper test -- will create events with gpsimes more than 2 seconds apart so that two groupers are created"
# fixing the simulate.py calling scripts to have the similar gpstimes so that the simulated events have similar gpstimes
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1L1_events.sh
    sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME.$RANDOM'/g' simulate_H1V1_event.sh
    sed -i -e 's/GPSTIME=0/GPSTIME='$((GPSTIME+2)).$RANDOM'/g' simulate_H1L1V1_events.sh
    ./simulate_H1L1_events.sh
    ./simulate_H1L1V1_events.sh
    ./simulate_H1V1_event.sh

else
    echo "Did not recognize grouper Test Type"

fi
