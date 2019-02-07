#!/usr/bin/python

import os, sys, re, time, platform, shutil
import subprocess
from datetime import datetime
from git import Repo


#stdout = sys.stdout
stdout = open(sys.__stdout__.fileno(),  # no wrapper around stdout which does LF translation
              mode=sys.__stdout__.mode,
              buffering=1,
              encoding=sys.__stdout__.encoding,
              errors=sys.__stdout__.errors,
              newline='\n',
              closefd=False)

additional_si_args = ""
project = sys.argv[1]
repo = None

def print_out(data):
    print(data, file=stdout)

def export_string(string):
    print_out('data %d\n%s' % (len(string), string))

def export_data(string):
    stdout.write('data %d\n' % len(string))
    stdout.buffer.write(string)
    stdout.write('\n')

def inline_data(filename, code = 'M', mode = '644'):

    content = open(filename, 'rb').read()
    if platform.system() == 'Windows':
        #this is a hack'ish way to get windows path names to work git (is there a better way to do this?)
        filename = filename.replace('\\','/')
    print_out("%s %s inline %s" % (code, mode, filename))
    export_data(content)

def si(command):
    #print("%s %s" % (datetime.now().strftime("%H:%M:%S"), command), file=sys.stderr)
    for i in range(20):
        # subprocess.getstatusoutput() below
        try:
            data = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
            exitcode = 0
        except subprocess.CalledProcessError as ex:
            data = ex.output
            exitcode = ex.returncode
        if data[-1:] == '\n':
            data = data[:-1]

        if exitcode == 0: break
        print(">>> Returned %d, trying again" % exitcode, file=sys.stderr)
        time.sleep(1)
    else: raise Exception("Command failed")
    return data.decode("cp850")


def convert_revision_to_mark(revision, allowNew, date=False):
    if revision in marks:
        return ":" + str(marks.index(revision) + 1)

    if allowNew:
        marks.append(revision)
        return ":" + str(len(marks))
    else:
        assert date, "No date given, cannot find commit"
        date = datetime.strftime(datetime.fromtimestamp(date), "%d.%m.%Y %X")
        commits = [c for c in repo.iter_commits("--all", before=date, after=date)]
        assert len(commits) == 1, "No commit found for date " + date
        return commits[0].hexsha


def retrieve_revisions(devpath=False):
    if devpath:
        devpath = '"' + devpath + '"'
    else:
        devpath = ":current"

    versions = si('si viewprojecthistory %s --quiet --rfilter=devpath:%s --project="%s"' % (additional_si_args, devpath, project))
    versions = versions.split('\n')
    versions = versions[1:]
    version_re = re.compile('[0-9]([\.0-9])+')

    revisions = []
    for version in versions:
        match = version_re.match(version)
        if match:
            version_cols = version.split('\t')
            revision = {}
            revision["number"] = version_cols[0]
            revision["author"] = version_cols[1]
            revision["seconds"] = int(time.mktime(datetime.strptime(version_cols[2], "%b %d, %Y %I:%M:%S %p").timetuple()))
            revision["tag"] = version_cols[5]
            revision["description"] = version_cols[6]
            revisions.append(revision)
        else: # append to previous description
            if not version: continue
            if revision["description"]: revision["description"] += '\n'
            revision["description"] += version

    revisions.reverse() # Old to new
    re.purge()
    return revisions

def retrieve_devpaths():
    devpaths = si('si projectinfo %s --devpaths --quiet --noacl --noattributes --noshowCheckpointDescription --noassociatedIssues --project="%s"' % (additional_si_args, project))
    devpaths = devpaths [1:]
    devpaths_re = re.compile('    (.+) \(([0-9][\.0-9]+)\)\n')
    devpath_col = devpaths_re.findall(devpaths)
    re.purge()
    devpath_col.sort(key=lambda x: [int(i) for i in x[1].split('.')]) #order development paths by version
    return devpath_col


def export_to_git(revisions, done_count, devpath=False, ancestor=False, ancestorDate=None):
    if len(revisions) == 0: return done_count

    abs_sandbox_path = os.getcwd()
    abs_sandbox_path = abs_sandbox_path.replace("\\", "/")
    integrity_file = os.path.basename(project)
    if not devpath: #this is assuming that devpath will always be executed after the mainline import is finished
        move_to_next_revision = False
    else:
        move_to_next_revision = True

    for revision in revisions:
        print("%d of %d (%f%%)" % (done_count, total_revision_count, done_count/total_revision_count*100), file=sys.stderr)
        done_count += 1

        mark = convert_revision_to_mark(revision["number"], True)
        if move_to_next_revision:
            si('si retargetsandbox %s --quiet --project="%s" --projectRevision=%s %s/%s' % (additional_si_args, project, revision["number"], abs_sandbox_path, integrity_file))
            si('si resync --yes --recurse %s --quiet --sandbox=%s/%s' % (additional_si_args, abs_sandbox_path, integrity_file))
        move_to_next_revision = True
        if devpath:
            print_out('commit refs/heads/devpath/%s' % devpath)
        else:
            print_out('commit refs/heads/master')
        print_out('mark %s' % mark)
        print_out('committer %s <> %d +0000' % (revision["author"], revision["seconds"]))
        export_string(revision["description"])
        if ancestor:
            print_out('from %s' % convert_revision_to_mark(ancestor, False, ancestorDate)) # we're starting a development path so we need to start from it was originally branched from
            ancestor = 0 #set to zero so it doesn't loop back in to here
        print_out('deleteall')
        tree = os.walk('.')
        for dir in tree:
            for filename in dir[2]:
                if (dir[0] == '.'):
                    fullfile = filename
                else:
                    fullfile = os.path.join(dir[0], filename)[2:]
                if (fullfile.find('.pj') != -1):
                    continue
                if (fullfile[0:4] == ".git"):
                    continue
                if (fullfile.find('mks_checkpoints_to_git') != -1):
                    continue
                inline_data(fullfile)

        if revision["tag"]:
            print_out('tag %s' % revision["tag"])
            print_out('from %s' % mark)
            print_out('tagger %s <> %d +0000' % (revision["author"], revision["seconds"]))
            export_string("") # Tag message

    print_out('checkpoint')
    return done_count

def createSandbox():
    if os.path.isdir("tmp"):
        shutil.rmtree("tmp")
    si('si createsandbox %s --populate --recurse --quiet --project="%s" --projectRevision=%s tmp' % (additional_si_args, project, revisions[0]["number"]))

def find_continuation_point(done_count, revisions):
    last_commit_date = repo.head.commit.committed_date
    revisions2 = [r for r in revisions if r["seconds"] > last_commit_date]
    done_count += len(revisions) - len(revisions2)
    return done_count, revisions2

def find_continuation_point_devpath(done_count, devpath2):
    branch = [ b for b in repo.branches if b.path == "refs/heads/devpath/" + devpath2[0][0]]
    if len(branch) == 0: return done_count, devpath2
    last_commit_date = branch[0].commit.committed_date
    revisions2 = [r for r in devpath2[1] if r["seconds"] > last_commit_date]
    done_count += len(devpath2[1]) - len(revisions2)
    devpath2 = devpath2[0], revisions2
    return done_count, devpath2

marks = []
all_revisions = retrieve_revisions()
done_count = 0
revisions = all_revisions[:]

devpaths = retrieve_devpaths()
devpaths2 = []
for devpath in devpaths:
    devpath2 = (devpath, retrieve_revisions(devpath[0]))
    all_revisions.extend(devpath2[1])
    devpaths2.append(devpath2)
total_revision_count = len(all_revisions)

devpaths3 = []
if os.path.isdir("tmp"):
    repo = Repo(".")
    done_count, revisions = find_continuation_point(done_count, revisions)
    for devpath2 in devpaths2:
        done_count, devpath3 = find_continuation_point_devpath(done_count, devpath2)
        devpaths3.append(devpath3)
else:
    createSandbox() # Create a build sandbox of the first revision

os.chdir('tmp')
done_count = export_to_git(revisions, done_count) #export master branch first!!

for devpath3 in devpaths3:
    revs = devpath3[1]
    branchname = devpath3[0][0].replace(' ','_')
    ancestor = devpath3[0][1]
    ancestorDate = [r for r in all_revisions if r["number"] == ancestor]
    assert len(ancestorDate) == 1, "Not exactly one ancestor with revision " + ancestor + " found, but " + str(len(ancestorDate))
    ancestorDate = ancestorDate[0]["seconds"]
    done_count = export_to_git(revs, done_count, branchname, ancestor, ancestorDate) #branch names can not have spaces in git so replace with underscores
os.chdir("..")

# Drop the sandbox
shortname=project.replace('"', '').split('/')[-1]
si("si dropsandbox --yes -f --delete=all tmp/%s" % (shortname))