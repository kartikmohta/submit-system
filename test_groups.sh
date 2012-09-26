#!/bin/bash

project=$1
user=$2
sendmail=$3

# Create temporary directory.
rundir=~/tmp_run/$project/$user

mkdir -p $rundir || exit 1
cd $rundir  || exit 1
pwd

python ~/class-monitor/check_groups.py ~/fall2011-projects/db/project_groups.db ~/submit/$project/$user > result.txt || exit 1

# Get email 
if [[ $user == *\.Z ]]
then
    echo "stripping username"
    user=${user%\.Z}
    echo "new username: $user"
fi

email=$user@seas.upenn.edu
if [ -e "./email.txt" ]
then
    email=`head -n 1 email.txt`
fi
echo "using email $email"

if [[ $email == web_* ]] 
then
    echo "ignoring web email $email"
fi

if [[ $sendmail == nomail ]]
then
    echo "SENDING MAIL DISABLED"
else
    echo "Sending email:"
    cat result.txt
    mail -s "CIS520: Group Submission Results" $email < result.txt
fi

# Cleanup
rm -rvf $rundir || exit 1
