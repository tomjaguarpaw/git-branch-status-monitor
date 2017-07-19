import getpass
import os
import tempfile
import smtp
import subprocess
import re

from subprocess import call

BEHIND       = 0
EQUAL_TO     = 1
AHEAD_OF     = 2
INCOMPARABLE = 3

REBASE_IS_CLEAN  = 4
REBASE_CONFLICTS = 5
MERGES_BETWEEN   = 6

def status_string(s):
    if s == BEHIND:
        return "BEHIND"
    elif s == EQUAL_TO:
        return "EQUAL_TO"
    elif s == AHEAD_OF:
        return "AHEAD_OF"
    elif s == REBASE_IS_CLEAN:
        return "REBASE_IS_CLEAN"
    elif s == REBASE_CONFLICTS:
        return "REBASE_CONFLICTS"
    elif s == MERGES_BETWEEN:
        return "MERGES_BETWEEN"

def status_action(s, b, r):
    if s == BEHIND:
        return '''Behind master.  Consider deleting it or rebasing master into it.

git stash && git checkout master && git branch -d %s && git push origin :%s

git stash && git fetch && git checkout %s && git rebase origin/master && git push
''' % (b, b, b)

    elif s == EQUAL_TO:
        return "Equal to master.  I like this branch :)"

    elif s == AHEAD_OF:
        return ('''Ahead of master.  I like this branch :)  Consider opening a merge request''')

    elif s == REBASE_IS_CLEAN:
        return '''Rebases cleanly on master.  Please perform the rebase ASAP!

git stash && git fetch && git checkout %s && git rebase origin/master && git push --force''' % b

    elif s == REBASE_CONFLICTS:
        return '''Rebase on master causes conflicts.  Please carefully rebase on master ASAP!

git stash && git fetch && git checkout %s && git rebase origin/master

    * If anything goes wrong do 'git --abort' and seek professional advice.

    * If it all goes right do 'git push --force\'''' % b

    elif s == MERGES_BETWEEN:
        return '''Ahead of master but contains merges.  Please perform the rebase ASAP!

git stash && git fetch && git checkout %s && git rebase origin/master

    * If anything goes wrong do 'git --abort' and seek professional advice.

    * If it all goes right do 'git push --force\'''' % b

def status(branch):
    c = compare_to_master(branch)

    if c == INCOMPARABLE:
        if can_rebase_cleanly_on_master(branch):
            s = REBASE_IS_CLEAN
        else:
            s = REBASE_CONFLICTS
    elif c == AHEAD_OF:
        if merges_between("origin/master", branch) == []:
            s = AHEAD_OF
        else:
            s = MERGES_BETWEEN
    else:
            s = c

    return s

def compare_to_master(branch):
    return compare(branch, "origin/master")

def compare(branch1, branch2):
    _1_lte_2 = is_ancestor_of(branch1, branch2)
    _2_lte_1 = is_ancestor_of(branch2, branch1)

    if _1_lte_2 and _2_lte_1:
        return EQUAL_TO
    elif not _1_lte_2 and _2_lte_1:
        return AHEAD_OF
    elif _1_lte_2 and not _2_lte_1:
        return BEHIND
    elif not _1_lte_2 and not _2_lte_1:
        return INCOMPARABLE
    else:
        raise Exception("Impossible situation!")

def is_ancestor_of(potential_ancestor, potential_descendant):
    r = call(["git", "merge-base", "--is-ancestor", potential_ancestor, potential_descendant])

    if r == 0:
        return True
    elif r == 1:
        return False
    else:
        raise ValueError("Didn't expect git merge-base --is-ancestor to return %s" % r)

'''Checks whether branch can be rebased cleanly on base'''
def can_rebase_cleanly_on(branch, base):
    call(["git", "checkout", "--quiet", branch])
    r = call(["git", "rebase", "--quiet", base])

    if r == 0:
        return True
    elif r == 128:
        call(["git", "rebase", "--abort"])
        return False
    else:
        raise ValueError("Didn't expect git rebase origin/master to return %s" % r)

def can_rebase_cleanly_on_master(branch):
    return can_rebase_cleanly_on(branch, "origin/master")

def match(s):
    m = re.match("^ *origin/([^ ]*)$", s)

    if m is not None:
        return m.group(1)
    else:
        return None

def origin_branches():
    process = subprocess.Popen(["git", "branch", "--remote"], stdout=subprocess.PIPE)
    (stdout, _) = process.communicate()

    stdout = stdout.decode("ascii")

    matches = [match(l) for l in stdout.splitlines()]

    matches_we_want = [m for m in matches if m is not None and m != 'master']

    return matches_we_want

def merges_between(commit1, commit2):
    process = subprocess.Popen(["git", "rev-list", "--merges", "%s..%s" % (commit1, commit2)], stdout=subprocess.PIPE)
    (stdout, _) = process.communicate()
    stdout = stdout.decode("ascii")
    return stdout.splitlines()

def output_repository(repo_name, repo):
    yield "\nRepo name: %s\n" % repo_name

    with tempfile.TemporaryDirectory() as dirpath:
        # Apparently to run a git clone we need to be in a
        # directory that exists!
        os.chdir("/")

        call(["git", "clone", "--quiet", repo, dirpath])

        os.chdir(dirpath)

        branches = origin_branches()

        results = [(branch, status_action(status("origin/" + branch), branch, repo_name))
                   for branch in branches]

        for r in results:
            yield "* %s: %s\n" % r

        for branch1 in branches:
            for branch2 in branches:
                c = can_rebase_cleanly_on("origin/" + branch1, "origin/" + branch2)

                if not c:
                    yield "WARNING: %s cannot be rebased cleanly on %s" % (branch1, branch2)

if __name__ == '__main__': main()
