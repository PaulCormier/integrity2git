#!/usr/bin/python

import os, sys, re, time, platform, shutil
import subprocess
import locale
from datetime import datetime
from git import Repo


assert os.path.isdir(".git"), "Call git init first"

#stdout = sys.stdout
stdout = open(sys.__stdout__.fileno(),  # no wrapper around stdout which does LF translation
              mode=sys.__stdout__.mode,
              buffering=1,
              encoding='utf8',  # Required for git fast-import
              errors=sys.__stdout__.errors,
              newline='\n',
              closefd=False)

additional_si_args = ""
project = sys.argv[1]

locale.setlocale(locale.LC_ALL, '')
# Check for a date format passed as a parameter
if sys.argv[2] == '--date-format':
    date_format = sys.argv[3]
else:
    date_format = '%x %X'


if not project.endswith("/project.pj"):
    project += "/project.pj"

def reencode(string):
    return string.encode("utf-8").decode(sys.__stdout__.encoding)
    
def print_out(data):
    print(data, file=stdout)

def trace(message):
    print("%s %s" % (datetime.now().strftime("%H:%M:%S"), message), file=sys.stderr)

def export_string(string):
    string = reencode(string)
    print_out('data %d\n%s' % (len(string), (string)))

def export_data(string):
    stdout.write('data %d\n' % len(string))
    stdout.buffer.write(string)
    stdout.write('\n')

def inline_data(filename, code = 'M', mode = '644'):

    content = open(filename, 'rb').read()
    if platform.system() == 'Windows':
        #this is a hack'ish way to get windows path names to work git (is there a better way to do this?)
        filename = filename.replace('\\','/')
    print_out("%s %s inline %s" % (code, mode, reencode(filename)))
    export_data(content)

def si(command):
    trace(command)
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
        print(">>> Returned %d: %s" % (exitcode, data), file=sys.stderr)
        print(">>> %s trying again" % datetime.now().strftime("%H:%M:%S"), file=sys.stderr)
        time.sleep(1)
    else:
        print_out('checkpoint')
        raise Exception("Command failed")
    return data.decode("cp850")
    

def retrieve_revisions(devpath=False):
    if devpath:
        devpath = '"' + devpath + '"'
    else:
        devpath = ":current"

    versions = si('si viewprojecthistory %s --quiet --rfilter=devpath:%s --project="%s"' % (additional_si_args, devpath, project))
    versions = versions.split('\n')
    versions = versions[1:]
    version_re = re.compile('^\d+(\.\d+)+\t')

    revisions = []
    for version in versions:
        match = version_re.match(version)
        if match:
            version_cols = version.split('\t')
            revision = {}
            revision["number"] = version_cols[0]
            revision["author"] = version_cols[1]
            revision["seconds"] = int(time.mktime(datetime.strptime(version_cols[2], date_format).timetuple()))
            revision["tags"] = [ v for v in version_cols[5].split(",") if v ]
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
    git_folder_re = re.compile("\.git(\\\|$)")  #any path named .git, with or without child elements. But will not match .gitignore
    
    if "ancestorDate" in revisions[0]:
        ancestor = revisions[0]["ancestor"]
        ancestorDate = revisions[0]["ancestorDate"]

    for revision in revisions:
        print("%d of %d (%0.2f%%)" % (done_count+1, total_revision_count, done_count/total_revision_count*100), file=sys.stderr)
        done_count += 1
        
        mark = marks[revision["number"]]
        si('si retargetsandbox %s --quiet --project="%s" --projectRevision=%s %s/%s' % (additional_si_args, project, revision["number"], abs_sandbox_path, integrity_file))
        si('si resync --yes --recurse %s --quiet --sandbox=%s/%s' % (additional_si_args, abs_sandbox_path, integrity_file))
        if devpath:
            print_out('commit refs/heads/devpath/%s' % devpath)
        else:
            print_out('commit refs/heads/master')
        print_out('mark %s' % mark)
        print_out('committer %s <> %d +0000' % (revision["author"], revision["seconds"]))
        export_string(revision["description"])
        if ancestor:
            print_out('from %s' % marks[ancestor]) # we're starting a development path so we need to start from it was originally branched from
            ancestor = False #set to zero so it doesn't loop back in to here
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
                #if (fullfile[0:4] == ".git"):
                if git_folder_re.search(fullfile):
                    continue
                if (fullfile.find('mks_checkpoints_to_git') != -1):
                    continue
                inline_data(fullfile)
        
        for tag in revision["tags"]:
            print_out('tag %s' % tag.replace(" ", "_"))
            print_out('from %s' % mark)
            print_out('tagger %s <> %d +0000' % (revision["author"], revision["seconds"]))
            export_string("") # Tag message

        re.purge()
    print_out('checkpoint')
    return done_count

repo = Repo(os.getcwd())
trace("Git directory: %s" % repo.common_dir)
def find_continuation_point(done_count, revisions):
    if not repo.head.is_valid(): return done_count, revisions
    last_commit_date = repo.head.commit.committed_date
    revisions2 = [r for r in revisions if r["seconds"] > last_commit_date]
    done_count += len(revisions) - len(revisions2)
    if len(revisions2) > 0:
        revisions2[0]["ancestor"] = revisions[done_count-1]["number"]
        revisions2[0]["ancestorDate"] = revisions[done_count-1]["seconds"]
    return done_count, revisions2

def find_continuation_point_devpath(done_count, devpath2):
    branch = [ b for b in repo.branches if b.path == "refs/heads/devpath/" + devpath2[0][0]]
    if len(branch) == 0:
        return done_count, { "info": devpath2[0], "revisions": devpath2[1] }
    last_commit_date = branch[0].commit.committed_date
    revisions2 = [r for r in devpath2[1] if r["seconds"] > last_commit_date]
    done_count += len(devpath2[1]) - len(revisions2)
    devpath3 = { "info": devpath2[0], "revisions": revisions2 }
    return done_count, devpath3

marks = {}
def create_marks(master_revisions, devpaths3):
    def convert_revision_to_mark(revision, allowNew, date=False):
        if revision in marks:
            return marks[revision]

        if allowNew:
            mark = ":" + str(len(marks)+1)
            marks[revision] = mark
            return mark
        else:
            assert date, "No date given, cannot find commit"
            date = datetime.strftime(datetime.fromtimestamp(date), date_format)
            commits = [c for c in repo.iter_commits("--all", before=date, after=date)]
            assert len(commits) == 1, "No commit found for date " + date
            marks[revision] = commits[0].hexsha
            return commits[0].hexsha
    
    if len(master_revisions) > 0:
        if "ancestorDate" in master_revisions[0]: # we are continuing master
            convert_revision_to_mark(master_revisions[0]["ancestor"], False, master_revisions[0]["ancestorDate"])
        for revision in master_revisions:
            convert_revision_to_mark(revision["number"], True)
    for devpath3 in devpaths3:
        convert_revision_to_mark(devpath3["info"][1], False, devpath3["ancestorDate"])
        for revision in devpath3["revisions"]:
            convert_revision_to_mark(revision["number"], True)

def check_tags_for_uniqueness(all_revisions):
    tags = {}
    for revision in all_revisions:
        for tag in revision["tags"]:
            tags.setdefault(tag, []).append(revision)
    error = False
    for tag, revisions in tags.items():
        if len(revisions) > 1:
            print(str(len(revisions)) + " revisions found for tag " + tag + ": " + ", ".join([ r["number"] for r in revisions ]), file=sys.stderr)
            error = True
    assert not error, "duplicate revisions"

all_revisions = retrieve_revisions()
revisions = all_revisions[:]

devpaths = retrieve_devpaths()
devpaths2 = []
for devpath in devpaths:
    devpath2 = (devpath, retrieve_revisions(devpath[0]))
    all_revisions.extend(devpath2[1])
    devpaths2.append(devpath2)
total_revision_count = len(all_revisions)
done_count = 0

check_tags_for_uniqueness(all_revisions)


devpaths3 = []
done_count, revisions = find_continuation_point(done_count, revisions)
for devpath2 in devpaths2:
    done_count, devpath3 = find_continuation_point_devpath(done_count, devpath2)
    devpath3["branchname"] = devpath3["info"][0].replace(' ','_') #branch names can not have spaces in git so replace with underscores
    ancestor = devpath3["info"][1]
    ancestorDate = [r for r in all_revisions if r["number"] == ancestor]
    assert len(ancestorDate) == 1, "Not exactly one ancestor with revision " + ancestor + " found, but " + str(len(ancestorDate))
    devpath3["ancestorDate"] = ancestorDate[0]["seconds"]
    devpaths3.append(devpath3)
trace("Found %d revisions and %d devapaths" % (len(revisions), sum([ len(dp["revisions"]) for dp in devpaths3 ]) ))
if len(revisions) == 0 and sum([ len(dp["revisions"]) for dp in devpaths3 ]) == 0:
    exit(0)

create_marks(revisions, devpaths3)
repo = None

if not os.path.isdir("tmp"):
    # Create a build sandbox of the first revision
    revision = None
    if len(revisions) > 0:
        revision = revisions[0]
    else:
        for devpath3 in devpaths3:
            if len(devpath3["revisions"]) > 0:
                revision = devpath3["revisions"][0]
                break

    si('si createsandbox %s --populate --recurse --quiet --project="%s" --projectRevision=%s tmp' % (additional_si_args, project, revision["number"]))

os.chdir('tmp')
done_count = export_to_git(revisions, done_count) #export master branch first!!

for devpath3 in devpaths3:
    ancestor = devpath3["info"][1]
    done_count = export_to_git(devpath3["revisions"], done_count, devpath3["branchname"], ancestor, devpath3["ancestorDate"])
os.chdir("..")

# Drop the sandbox
shortname=project.replace('"', '').split('/')[-1]
si("si dropsandbox --yes -f --delete=all tmp/%s" % (shortname))