#!/bin/bash

while true; do
    ./monitor_ssh_location.py $*
    echo "Finished."
    killall MATLAB
    sleep 10
done

