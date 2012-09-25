#!/bin/bash

project=$1
failed=`grep $2 db/cis520.$1 | awk -F ',' '{print $1}'`
echo $failed
for f in $failed
do
    cat ~/project_logs/$3.$1.$f
done
