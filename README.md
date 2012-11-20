submit-system
=============

A set of tools for monitoring a location on the filesystem and
forking controlled processes whenever changes occur within some specificiations.

Installation
------------

To install, you need to have:

* Cloned the git to any directory
* Created a directory for the monitor output in ~/html/monitor
* Setup the `turnin/project` system set up to put submissions in the `~/submit/` folder, or any other means of getting submissions to that folder
* Some testing script you'd like to execute when new submissions appear
* A configuration .ini file (see cis520.ini for an example) pointing to the right ~/submit folders and pointing to the script you'd like to run when new submissions appear in that folder.

Then:

* Setup a `screen` session or other means of maintaining a console indefinitely.
* Run the command `run_monitor_many_times.sh <yourconfig>.ini`

Now the system will be up and running, baring any major errors. Whenever it detects a new tar or file appearing in a location it's monitoring, it will update the status at ~/html/monitor, send an email to the user, and fork a process to call the appropriate script.

This system works well with my `matlab-autograder` (https://github.com/djweiss/matlab-autograder) for Matlab based courses.