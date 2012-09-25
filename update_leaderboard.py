#!/usr/bin/env python
# Created Aug 2011
# Author: David Weiss
#
# Keeps a leaderboard updated Netflix style.

# Hardcoded configuration

from datetime import *
import sys, csv, time, subprocess, os
import tarfile, math, pickle

VERSION = "1.1"

LEADERBOARD_PAGE = "/home1/c/cis520/html/fall11/leaderboard.html"
#LEADERBOARD_PAGE = "test/leaderboard.html"

MIN_TIME = 60*60*5 # once every 5 hours
#MIN_TIME = 0

TEST_SET = 0
QUIZ_SET = 1

PAGE_TITLE_HTML =  """
  <h1>Leaderboard for CIS520 Final Project</h1>
  <h4>Updated: {updated}, version {version}</h4>
  <p>Click on the header of any column to sort by that column.</p>
"""

SUBMISSION_ROW_HTML = """
<tr>
  <td>{name}</td>
  <td>{submitted}</td>
  <td>{accuracy:.2%}</td>
  <td>{rmse:.4f}</td>
  <td>{best_rmse:.4f}</td>
</tr>
"""

class LeaderBoard:
    def __init__(self, dbfile):
        self.dbfile = dbfile
        if os.path.exists(dbfile):
            self.db = pickle.load(file(dbfile, 'r'))
        else:
            self.db = {}

    def get(self, name):
        return self.db.get(name)

    def update(self, name, submitted, accuracy, rmse):

        if self.db.has_key(name):
            old_rec = self.db[name]
            old_rmse = old_rec['rmse']

            # convert between old and new format
            if len(old_rmse) == 2:
                old_rmse.append(old_rmse[QUIZ_SET])

            # keep the best RMSE so far
            if rmse[QUIZ_SET] > old_rmse[2]:
                rmse.append(old_rmse[2])
            else:
                rmse.append(rmse[QUIZ_SET])

        else:
            rmse.append(rmse[QUIZ_SET])

        self.db[name] = {'name': name, 'submitted': submitted,
                         'accuracy': accuracy, 'rmse': rmse}

        pickle.dump(self.db, file(self.dbfile, 'w'))
        
class GroupLookup:
    def __init__(self, dbfile):
        self.db = pickle.load(file(dbfile, 'r'))
    
    def get(self, name):
        return self.db['users'].get(name)
    
    def members(self, name):
        return self.db['groups'].get(name)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print "usage: %s <groups.db> <leaderboard.db> <answers.db> <path_to_submission>" % sys.argv[0]
        sys.exit(1)

    for i in [1, 3, 4]:
        if not os.path.exists(sys.argv[i]):
            sys.stderr.write( "error: %s does not exist\n" % sys.argv[i] )
            sys.exit(1)

    groups = GroupLookup(sys.argv[1])
    leaderboard = LeaderBoard(sys.argv[2])

    # Check for valid group
    (submission_path, submission_ext) = os.path.splitext(sys.argv[4])

    username = os.path.basename(submission_path)
    groupname = groups.get(username)

    if groupname is None:
        sys.stderr.write("Error: username %s has no group\n"  % username)
        sys.exit(1)

    members = groups.members(groupname)
    if len(members) > 3 or len(members) < 2:
        sys.stderr.write("Error: team '%s' has %d members, which is not in the allowable range." % (groupname, len(members)))
        sys.exit(1)

    # Check that enough time has passed since the last submission
    last_submission = leaderboard.get(groupname)
    if last_submission is not None and (time.time()-last_submission['submitted']) < MIN_TIME:
        sys.stderr.write("Error: it has only been %d seconds since your last submission. (Submissions allowed every %d seconds.)\n" 
                         % (int(time.time()-last_submission['submitted']), MIN_TIME))
        sys.exit(1)

    # Read the submission
    submission = None

    # Untar first
    tar = tarfile.open(name=sys.argv[4])
    submission = tar.extractfile("submit.txt")
    if submission is None:
        sys.stderr.write( "Error: submission does not contain submit.txt!\n" )
        sys.exit(1)

    submit = submission.readlines()
    answers = file(sys.argv[3], 'r').readlines()

    # Compute accuracy and RMSE
    if len(submit) != len(answers):
        sys.stderr.write("Error: Submission must be %d lines, not %d.\n" % (len(answers), len(submit)))
        sys.exit(1)

    accuracy = [0, 0]
    rmse = [0, 0]
    n = [0, 0]
    for i in range(0, len(answers)):
        guess = submit[i].split()[0]
        (truth, is_quiz) = answers[i].split()
        
        guess = float(guess)
        truth = float(truth)
        is_quiz = int(is_quiz)

        n[is_quiz] += 1
        accuracy[is_quiz] += float(round(guess) == round(truth))
        rmse[is_quiz] += (guess-truth)**2

    for i in range(0,len(n)):
        accuracy[i] = accuracy[i] / float(n[i])
        rmse[i] = math.sqrt(rmse[i]/float(n[i]))
    
    leaderboard.update(name=groupname, submitted=time.time(),
                       accuracy=accuracy, rmse=rmse)

    # Render the leaderboard
    rows_html = ""

    recs = leaderboard.db.values()
    recs.sort(key= lambda x: float(x['rmse'][-1]), reverse=False) 

    for rec in recs:
        rows_html += SUBMISSION_ROW_HTML.format(
            name=rec['name'], submitted=time.ctime(rec['submitted']),
            accuracy=rec['accuracy'][QUIZ_SET], rmse=rec['rmse'][QUIZ_SET], 
            best_rmse=rec['rmse'][-1])
        rows_html += "\n"

    rows_html += "</table>\n"

    title_html = PAGE_TITLE_HTML.format(version=VERSION, 
                                        updated=time.ctime())

    print "*"*72
    print "Your project results as of %s:" % time.ctime()
    print "*"*72
    print "Team: " + groupname
    print "Accuracy: {0:.2%}, RMSE: {1:.2f}".format(accuracy[QUIZ_SET], rmse[QUIZ_SET])

    HEADER_HTML = """
<html>
<head>
  <title>Project Leaderboard</title>
  <META HTTP-EQUIV="expires" CONTENT="0">
  <script src="sorttable.js"></script>
  <style type="text/css">
    body 
    { 
    font-family: helvetica, sans-serif;
    font-size: 12px;
    }

    h1 { 
    letter-spacing: -1px;
    font-size:25px;
    }
    
    h2 { 
    font-size: 20px;
    letter-spacing: -1px;
    color: #034769;
    border-bottom: 1px solid #034769;
    }
    
    h4 {
    font-size: 14px;
    font-style: italic;
    }
    
    table { 
    text-align: center;
    font-size: 1.2em;
    margin: 15px auto;
    border: 1px solid black;
    } 
    table th { 
    color: white;
    background-color: #034769;
    padding: 2px 5px;
    }
    table td { 
    padding: 2px 5px;
    }
  </style>
</head>
<body>
"""
    FOOTER_HTML = """
</body>
</html>
"""
    SUBMISSION_TABLE_HTML = """
<table class="sortable">
<tr>
  <th>Group Name</th>
  <th>Time Submitted</th>
  <th>Accuracy</th>
  <th>RMSE</th>
  <th>Best RMSE</th>
</tr>
"""
    leaderboard_html = file(LEADERBOARD_PAGE, 'w')
    leaderboard_html.write(HEADER_HTML + title_html + SUBMISSION_TABLE_HTML
                           + rows_html + FOOTER_HTML)
    leaderboard_html.close()


    
    

        
        
        

    
    
    
        

    
    


