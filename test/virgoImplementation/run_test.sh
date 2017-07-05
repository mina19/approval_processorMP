# source all of the testing repositories
source setup.sh

# send one fake CWB event which is a triple
# Joint FAP high enough and IS NOT vetoed
# G000000
# Should be labeled EM_READY
./one_fake_cwb_virgodq.sh

sleep 5
./resetThrottleBurst.sh

# send one fake CWB event which is a triple
# Joint FAP high enough and IS vetoed
# G000001
# Should be labeled DQV
sed -i -e 's/VIRGODQRESPONSE=1/VIRGODQRESPONSE=0/g' one_fake_cwb_virgodq.sh
./one_fake_cwb_virgodq.sh

sleep 5
./resetThrottleBurst.sh

# send one fake CWB event which is a triple
# Joint FAP too low and IS NOT vetoed
# G000002
# Should be labeled DQV
sed -i -e 's/VIRGODQRESPONSE=0/VIRGODQRESPONSE=1/g' one_fake_cwb_virgodq.sh
sed -i -e 's/IDQ_RESPONSE=1/IDQ_RESPONSE=0/g' one_fake_cwb_virgodq.sh
./one_fake_cwb_virgodq.sh

sleep 5
./resetThrottleBurst.sh

# send one fake CWB event which is a triple
# Joint FAP too low and IS vetoed
# G000003
# Should be labeled DQV
sed -i -e 's/VIRGODQRESPONSE=1/VIRGODQRESPONSE=0/g' one_fake_cwb_virgodq.sh
./one_fake_cwb_virgodq.sh

sleep 5
./resetThrottleBurst.sh

# send one fake gstlal event which is a triple
# IS NOT vetoed
# G000004
# Should be labeled EM_READY
./one_fake_gstlal_virgodq.sh

sleep 5
./resetThrottleCBC.sh

# send one fake gstlal event which is a triple
# IS vetoed
# G000005
# Should be labeled DQV
sed -i -e 's/VIRGODQRESPONSE=1/VIRGODQRESPONSE=0/g' one_fake_gstlal_virgodq.sh
./one_fake_gstlal_virgodq.sh

sleep 5
./resetThrottleCBC.sh

# send one fake CWB event which is a double H1 L1
# Joint FAP high enough
# G000006
# Should be labeled EM_READY
./one_fake_cwb_double.sh

sleep 5
./resetThrottleBurst.sh

# send one fake CWB event which is a double H1 L1
# Joint FAP too low
# G000007
# Should be labeled DQV
sed -i -e 's/IDQ_RESPONSE=1/IDQ_RESPONSE=0/g' one_fake_cwb_double.sh
./one_fake_cwb_double.sh

sleep 5
./resetThrottleBurst.sh

# send one fake gstlal event which is a double H1 L1
# G000008
# Should be labeled EM_READY
./one_fake_gstlal_double.sh

sleep 5
./resetThrottleCBC.sh





