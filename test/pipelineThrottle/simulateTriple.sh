# source all of the testing repositories
source setup.sh


# send one fake CBC_gstlal_LowMass event which is a triple
# this event should *not* be labeled as EM_Throttled
# should pass ifosCheck
./one_fake_gstlal_triple.sh

sleep 30

# send one fake CBC_gstlal_LowMass event which is a double
# involving V1
# this should *NOT* be labelled EM_Throttled but 
# should fail ifosCheck
./one_fake_gstlal_double_V1.sh
