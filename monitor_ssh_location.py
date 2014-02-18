#!/usr/bin/env python
# Created Aug 2011
# Author: David Weiss
#
# A class to monitor a remote SSH location and run a designated script
# every time a target file changes. Also maintains status page at
# remote location.
#
# TODO: - add emailing when assignments picked up.
# TODO: - add emailing when assignments fail.

from datetime import *
import sys, csv, time, subprocess, os
import paramiko
import ConfigParser

VERSION = "0.8"

PAGE_TITLE_HTML =  """
  <h1>Submission monitor: {username}</h1>
  <h4>Updated: {updated}, version {version}</h4>
"""

PROJECT_TABLE_HTML = """
<table>
<tr>
  <th>Project</th>
  <th>Submissions</th>
  <th>Queued</th>
  <th>Completed</th>
  <th>Running</th>
  <th>Failed</th>
</tr>
"""

PROJECT_ROW_HTML = """
<tr>
  <td><a href=\"{name}.html\">{name}</a></td>
  <td>{num_submissions}</td>
  <td>{num_queued}</td>
  <td>{num_completed}</td>
  <td>{num_running}</td>
  <td>{num_failed}</td>
</tr>"""

SUBMISSION_TABLE_HTML = """
<table>
<tr>
  <th>Name</th>
  <th>Size</th>
  <th>Time Submitted</th>
  <th>Status</th>
</tr>
"""

SUBMISSION_ROW_HTML = """
<tr>
  <td>{name}</td>
  <td>{size}</td>
  <td>{submitted}</td>
  <td>{status}</td>
</tr>
"""

class ProjectConfig:
    def __init__(self, name, action, size_limit, time_limit):
        self.name = name              
        self.action = action
        self.size_limit = size_limit
        self.time_limit = time_limit
        
class MonitorConfig:
    def __init__(self, filename):

        config = ConfigParser.ConfigParser()
        print "Loading configuration from: %s" % filename
        config.read(filename)
        self.target_dir = config.get('Monitor', 'target_dir')
        self.username = config.get('Monitor', 'username')
        self.is_local = config.getboolean('Monitor', 'is_local')
        self.log_dir = config.get('Monitor', 'log_dir')
        if not os.path.exists(self.log_dir):
            try:
                os.mkdir(self.log_dir)
            except OSError:
                print "Unable to create log directory: %s" % self.log_dir
                sys.exit(1)
                
        if not self.is_local:
            self.hostname = config.get('Monitor', 'hostname')
            self.private_key_file = config.get('Monitor', "private_key_file")
            self.private_key_passphrase =  config.get('Monitor', 'private_key_passphrase')

        self.website_path = config.get('Monitor','website_path')
        self.website_header = config.get('Monitor', 'website_header')
        self.website_footer = config.get('Monitor', 'website_footer')
        self.notify_queue = config.get('Monitor', 'notify_queue')
        self.notify_action = config.get('Monitor', 'notify_action')
        self.notify_complete = config.get('Monitor', 'notify_complete')

        project_sections = [section for section in config.sections()
                            if section.startswith('Project')]
        assert len(project_sections) > 0, "must have at least one project to monitor"

        self.projects = []
        for project in project_sections:
            print "Found project: %s = %s " % (project , config.get(project, 'name'))
            self.projects.append(ProjectConfig(
                    config.get(project, 'name'),
                    config.get(project, 'action'),
                    config.getfloat(project, 'size_limit'),
                    config.getfloat(project, 'time_limit')))

class MonitorSSHLocation:
    def __init__(self, config):
        self.config = config

        # initialize empty database etc.
        self.action_queue = list()
        self.project_data = {}
        for project in self.config.projects:
            self.project_data[project.name] = {}

        self.db_keys = ['name','size','updated', 'timestamp', 'status']

    def SendEmail(self, rcpt, subj, txt):
        if rcpt.startswith("web_"):
            print "Ignoring email to rcpt %s" % rcpt
            return

        # write tmp email body
        f = file('tmp_email_body.txt', 'w')
        f.write(txt)
        f.close()
        cmd = 'mail -c "" -s "%s: %s" %s < tmp_email_body.txt' % (self.config.username, subj, rcpt)
        os.system(cmd)
                
    def GetActionQueue(self):

        file_manager = os

        if not self.config.is_local:
            # Initialize SSH connection to target server.
            print "Connecting to server: %s@%s" % (self.config.username, self.config.hostname)
            private_key = paramiko.RSAKey.from_private_key_file(
                self.config.private_key_file, 
                self.config.private_key_passphrase)
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=self.config.hostname,
                           username=self.config.username,
                           pkey=private_key)
            file_manager = client.open_sftp()

        # Get list of projects from the server and compare with
        # projects we are supposed to be monitoring.
        print "Getting list of projects in directory: %s" % self.config.target_dir
        dirlist = file_manager.listdir(self.config.target_dir)
        project_names = [p.name for p in self.config.projects]
        active_projects = set(project_names).intersection(set(dirlist))

        print "Found %d active projects: %s" % (len(active_projects), 
                                                ','.join(active_projects))

        # For each active project, check the submissions against the databse.
        for project in active_projects:

            # Check for projects with the same name.
            project_cfg = [p for p in self.config.projects if p.name == project]
            if len(project_cfg) > 1:
                print "ERROR ERROR MORE THAN ONE PROJECT FOUND"
            project_cfg = project_cfg[0]

            submission_attr = list()
            project_dir = self.config.target_dir + "/" + project
            if not self.config.is_local:
                submission_attr = file_manager.listdir_attr(project_dir)
            else:
                #submission_filenames = file_manager.listdir(project_dir)
                mtime = lambda f: file_manager.stat(project_dir+"/"+f).st_mtime
                submission_filenames = sorted(file_manager.listdir(project_dir),
                        key=mtime) # Sort to choose oldest submission first
                for filename in submission_filenames:
                    stat = paramiko.SFTPAttributes.from_stat(file_manager.stat(
                            project_dir + "/" + filename))
                    stat.filename = filename
                    submission_attr.append(stat)
                
            print "%s: Found %d submissions." % (project, len(submission_attr))

            for submission in submission_attr:

                # Check for newer than previous
                submit_time = datetime.fromtimestamp(int(submission.st_mtime))
                if self.GetMostRecentlyModified(project, submission) < submit_time:
                    # Check for over file limit
                    if int(submission.st_size) > (project_cfg.size_limit*1e6):
                        self.UpdateDatabase(project, submission, 'file_too_large')
                        action = {'submission': submission, 'project': project}
                        data = self.project_data[project][submission.filename]
                        self.SendFailureEmail(action, data, append_log=False)
                    else:
                        self.AddToActionQueue(project_cfg, submission)

                # Otherwise, do nothing.

    def GetMostRecentlyModified(self, project, submission):
        # If a new submission, beginning of time
        if not self.project_data[project].has_key(submission.filename):
            return datetime.fromtimestamp(0)

        # Otherwise, return the time stamp
        return datetime.fromtimestamp(
            int(float(self.project_data[project][submission.filename]['timestamp'])))

    def UpdateDatabase(self, project, submission, status_str):
        if not self.project_data[project].has_key(submission.filename):
            self.project_data[project][submission.filename] = {}
        
        data = self.project_data[project][submission.filename]
        data['updated'] = str(int(time.time()))
        data['timestamp'] = str(int(submission.st_mtime))
        data['status'] = status_str
        data['size'] = "%.4f" % (int(submission.st_size)/1e6)
        data['name'] = submission.filename;

        self.UpdateWebsite()

    def WriteDatabase(self):
        for project in self.config.projects:
            db = self.project_data[project.name]
            dbfile = file('./db/' + '.'.join([self.config.username, project.name]),'w')
            print "Updating database: %s" % dbfile.name

            for submit_key in db.keys():
                rec = db[submit_key]
                row = []
                for key in self.db_keys:
                    row.append(rec[key])

                dbfile.write(','.join(row) + '\n')
            dbfile.close()
            
    def LoadDatabase(self):
        for project in self.config.projects:
            filename = './db/' + '.'.join([self.config.username, project.name])
            if os.path.exists(filename):
                dbfile = file(filename,'r')
                print "Reading database: %s" % dbfile.name
                db = self.project_data[project.name]
                db.clear()
                reader = csv.reader(dbfile, delimiter=',')
                for row in reader:
                    rec = {}
                    for i in range(len(self.db_keys)):
                        rec[self.db_keys[i]] = row[i]
                        
                    db[rec['name']] = rec
                    print rec
        
        self.UpdateWebsite()

    def AddToActionQueue(self, project_cfg, submission):
        self.UpdateDatabase(project_cfg.name, submission, 'queued');
        self.action_queue.append({
                'executable': project_cfg.action,
                'project': project_cfg.name, 
                'submission': submission,
                'timeout': project_cfg.time_limit})

    def UpdateWebsite(self): 
        
        webroot = self.config.website_path
        index_fp = file(webroot + "/index.html", "w");
        project_fp = {}
        for project in self.config.projects:
            project_fp[project.name] = file(webroot + "/" + project.name + 
                                            ".html", "w")
        header_html = file(self.config.website_header, "r").read()
        footer_html = file(self.config.website_footer, "r").read()
        title_html = PAGE_TITLE_HTML.format(username=self.config.username,
                                            version=VERSION,
                                            updated=str(datetime.now()))
        
        # Update master index page.
        index_fp.write(header_html + title_html + PROJECT_TABLE_HTML)
        index_fp.write("<h2>Project Overviews</h2>")
        for project in self.config.projects:
            data = sorted(self.project_data[project.name].values(),
                    key=lambda x: x['name']) # Sort by name
            num_queued = len(
                [a for a in data if a['status'] == 'queued'])
            num_completed = len(
                [a for a in data if a['status'] == 'completed'])
            num_running = len(
                [a for a in data if a['status'] == 'running'])
            num_failed = len(
                [a for a in data if a['status'].startswith('failed') or 
                 a['status'] == 'killed' or a['status'] == 'file_too_large'])

            num_submissions = len(self.project_data[project.name].keys())
            index_fp.write(PROJECT_ROW_HTML.format(
                    name=project.name, num_submissions=num_submissions,
                    num_queued=num_queued, num_completed=num_completed, 
                    num_running=num_running, num_failed=num_failed))

            # Update project website.
            fp = project_fp[project.name]
            fp.write(header_html + title_html)
            fp.write("<p><a href='index.html'>Back to Overview</a></p>")
            fp.write("<h2>Project Submissions: %s</h2>\n" % project.name)
            fp.write(SUBMISSION_TABLE_HTML)
            for row in data:
                fp.write(SUBMISSION_ROW_HTML.format(
                        name=row['name'],
                        size=row['size'] + ' MB', 
                        submitted=str(
                            datetime.fromtimestamp(float(row['timestamp']))),
                        status=row['status'] + ' (' + 
                        str(datetime.fromtimestamp(float(row['updated']))) + ')'))
            fp.write('\n</table>\n\n' + footer_html)
            fp.close()

        index_fp.write("\n</table>\n\n" + footer_html)
        index_fp.close()

    def GetEmail(self, action):
        filename = action['submission'].filename
        if filename.endswith('.Z'):
            username = filename[:-2]
        else:
            username = filename
            
        email = username + "@seas.upenn.edu"
        return email

    def SendFailureEmail(self, action, data, append_log=True):
        email = self.GetEmail(action)

        filename = action['submission'].filename
        txtstr = "Dear %s," % email
        txtstr += "Your submission to project %s has failed to execute.\n" % action['project']
        txtstr += "The reason: %s\n" % data['status'] 
        txtstr += "Please forward this email to the TA if you don't understand the problem.\n"
        txtstr += "\n---------------- DATABASE ENTRY: \n"
        txtstr += str(data)

        if append_log:
            txtstr += "\n---------------- STDOUT: \n"
            txtstr += ''.join(file(action['stdout'], 'r').readlines())
            txtstr += "\n---------------- STDERR: \n"
            txtstr += ''.join(file(action['stderr'], 'r').readlines())

        self.SendEmail(email, "Submission Failure", txtstr)

    def ExecuteActions(self):
        print "%d actions remain in queue." % len(self.action_queue)

        # Send email notification that action has been picked up.
        for i in range(0, len(self.action_queue)):
            action = self.action_queue[i]
            email = self.GetEmail(action)
            txtstr = "Dear %s," % email
            txtstr += "Your submission to project %s has been received.\n" % action['project']
            txtstr += "There are %d submissions ahead of you in line.\n" % (len(self.action_queue)-i-1)
            self.SendEmail(email, "Submission Received", txtstr)

        for action in self.action_queue:
            project = action['project']
            filename = action['submission'].filename
            args = [action['executable'], project, filename]
            print "Executing action: %s" % ' '.join(args)

            action['stdout'] = '%s/stdout.%s.%s' % (self.config.log_dir, project, filename)
            action['stderr'] = '%s/stderr.%s.%s' % (self.config.log_dir, project, filename)
            try:
                os.remove(action['stdout'])
                os.remove(action['stderr'])
                print "removed log %s" % action['stdout']
                print "removed log %s" % action['stderr']
            except OSError as err:
                print "could not remove logs: %s" % str(err)

            stdout = file(action['stdout'], 'w')
            stderr = file(action['stderr'], 'w')

            start_time = time.time()
            self.UpdateDatabase(project, action['submission'], 'running');
            p = subprocess.Popen(args, stdout=stdout, stderr=stderr)

            kill = False
            while not kill and (p.poll() == None):
                # Check very 1s if process is still running.
                elapsed = (time.time() - start_time)
                if  elapsed > action['timeout']:
                    kill = True
                    print "Process is overtime after %.2f secs" % elapsed
                else:
                    time.sleep(0.1)

            if kill:
                p.kill()
                print "Killed process: %d" % p.pid
                os.system("killall MATLAB");
                self.UpdateDatabase(project, action['submission'], 'killed')
            else:
                print "Action returned with code: %d" % p.returncode
                if p.returncode == 0:
                    self.UpdateDatabase(project, action['submission'], 'completed')
                else:
                    self.UpdateDatabase(project, action['submission'], 
                                        'failed(%d)' % p.returncode)

            stdout.close()
            stderr.close()
            data = self.project_data[project][action['submission'].filename]
            if not data['status'] == 'completed':
                self.SendFailureEmail(action, data, 
                                      append_log=data['status'] != 'killed')


            

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print "usage: %s <config.ini>" % sys.argv[0]
    else:
        monitor = MonitorSSHLocation(MonitorConfig(sys.argv[1]))
        monitor.LoadDatabase()
        monitor.GetActionQueue()
        monitor.ExecuteActions()
        monitor.WriteDatabase()


# Monitor "submit" directory -- monitoring multiple projects.
# Check last updated time of each file in each directory.
# If it's a new file, run the script and store in the database.
# Database format: csv file.
# Each project is a subdirectory of submit.
# Each project can have an associated script to be run for each user.
# This is then output to
