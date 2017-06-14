# source all of the testing repositories
source setup.sh

# send three fake CBC_gstlal_LowMass events, to trip the throttle
# these three events should be labeled as EM_Throttled
./three_fake_gstlal.sh

# wait 60 seconds
sleep 60

# send resetThrottle command for this pipelineKey
./resetThrottleTest.sh

# wait a few seconds
sleep 20

# send one fake CBC_gstlal_LowMass event
# this event should *not* be labeled as EM_Throttled
./one_fake_gstlal.sh
