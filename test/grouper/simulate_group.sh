#!/bin/bash

# call the scripts that create the config files
./one_fake_cwb_double.sh
./one_fake_cwb_virgodq.sh
./one_fake_gstlal_double.sh
./one_fake_gstlal_double_V1.sh
./one_fake_gstlal_triple.sh

GPSTIME="`tconvert now`"
echo $GPSTIME

# fixing the simulate.py calling scripts to have the same gpstime so that the simulated events have similar gpstimes
sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME'/g' simulate_H1L1_events.sh
sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME'/g' simulate_H1V1_event.sh
sed -i -e 's/GPSTIME=0/GPSTIME='$GPSTIME'/g' simulate_H1L1V1_events.sh

# now calling the scripts to simulate the triggers with the altered gpstimes
./simulate_H1L1_events.sh
./simulate_H1L1V1_events.sh
./simulate_H1V1_event.sh

# fixing simulate.py calling scripts to that we can use this script again
sed -i -e 's/GPSTIME='$GPSTIME'/GPSTIME=0/g' simulate_H1L1_events.sh
sed -i -e 's/GPSTIME='$GPSTIME'/GPSTIME=0/g' simulate_H1V1_event.sh
sed -i -e 's/GPSTIME='$GPSTIME'/GPSTIME=0/g' simulate_H1L1V1_events.sh

