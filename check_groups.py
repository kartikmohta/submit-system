#!/usr/bin/env python
# Created Aug 2011
# Author: David Weiss
#
# Keeps tabs on group projects.

from datetime import *
import sys, csv, time, subprocess, os
import tarfile
import pickle

VERSION = "1.0"

if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.stderr.write( "usage: %s <groups.db> <path_to_submission>" % sys.argv[0] )
        sys.exit(1)
        
    db  = {'users': {}, 'groups': {}}

    if os.path.exists(sys.argv[1]):
        db = pickle.load(file(sys.argv[1]))

    if not os.path.exists(sys.argv[2]):
        sys.stderr.write( "error: %s does not exist" % sys.argv[2] )
        sys.exit(1)

    # Parse answers
    (submission_path, submission_ext) = os.path.splitext(sys.argv[2])

    submission = None
    username = os.path.basename(submission_path)

    # Untar first
    tar = tarfile.open(name=sys.argv[2])
    submission = tar.extractfile("group.txt")
    if submission is None:
        sys.stderr.write( "Error: submission does not contain group.txt!" )
        sys.exit(1)

    groupname = submission.readlines()
    if len(groupname) != 1:
        sys.stderr.write( "Error: submission should contain only a single line.")
        sys.exit(1)

    groupname = groupname[0]
    if groupname[-1] == '\n':
        groupname = groupname[0:-1]
    
    users = db['users']
    groups = db['groups']
    if users.get(groupname) is not None:
        sys.stderr.write( "Error: invalid groupname %s; this belongs to a username" % groupname )
        sys.exit(1)

    if users.get(username) is not None:
        members = groups.get(users.get(username))
        if members is None or username not in members:
            sys.stderr.write( "Error: Database is corrupt: user %s has no group" % username)
            sys.exit(1)
        members.remove(username)

    members = groups.get(groupname, set())
    members.add(username)
    groups[groupname] = members
    users[username] = groupname
    pickle.dump(db, file(sys.argv[1], 'w'))

    print "Membership for username: %s" % username
    print "Group: %s" % groupname
    print "Members: %s" % ', '.join(members)
    
