import argparse
import collections
import configparser
from datetime import datetime
import grp, pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os
import re
import sys
import zlib

argparser = argparse.ArgumentParser(description="The stupidist content tracker")
argsubparsers = argparser.add_subparsers(title='Commands', dest='command')
argsubparsers.required = True

argsp = argsubparsers.add_parser("init", help="Initialize a new empty, repository.")
argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository. ")
argsp = argsubparsers.add_parser("cat_file", help="Provide content for repository objects")
argsp.add_argument("type",
                   metavar="type",
                   choices=['blob', 'commit', 'tag', 'tree'],
                   help='Specify the type')
argsp.add_argument("object",
                   metavar="object",
                   help="The object to display")

argsp = argsubparsers.add_parser("hash_object", help="compute object id and optionally creates a blob from a file")
argsp.add_argument("-t",
                   metavar='type',
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default="blob",
                   help="specify the type")
argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="Actually write the object into the database")
argsp.add_argument("path",
                   help="Read object from file <file>")

argsp = argsubparsers.add_parser("log", help="Display history of a given commit")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="commit to start at.")



def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())

def object_find(repo, name, fmt=None, follow=True):
    return name

def cmd_init(args):
    repo_create(args.path)

def cmd_hash_object(args):
    if args.write:
        repo = repo_find()
    else:
        repo = None
    
    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


def cmd_log(args):
    repo = repo_find()

    print("digraph wyaglog{")
    print(" node[shape=rect]")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")


def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    short_hash = sha[0:8]
    message = commit.kvlm[None].decode("utf8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace("\"", "\\\"")

    if "\n" in message: # keep only the first line
        message = message[:message.index("\n")]
    
    print("  c_{0} [label=\"{1}: {2}\"]".format(sha, sha[0:7], message))
    assert commit.fmt==b'commit'

    if not b'parent' in commit.kvlm.keys():
        # Base case: the initial commit.
        return

    parents = commit.kvlm[b'parent']

    if type(parents) != list:
        parents = [ parents ]

    for p in parents:
        p = p.decode("ascii")
        print ("  c_{0} -> c_{1};".format(sha, p))
        log_graphviz(repo, p, seen)
        

def object_hash(fd, fmt, repo=None):
    """hash object, writing it to repo if provided"""
    data = fd.read()
    
    # choose constructor according to fmt argument
    match fmt:
        case b'commit'   : obj=GitCommit(data)
        case b'tree'     : obj=GitTree(data)
        case b'tag'      : obj=GitTag(data)
        case b'blob'     : obj=GitBlob(data)
    
    return object_write(obj, repo)


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    match args.command:
        case "add"                : cmd_add(args)
        case "cat-file"           : cmd_cat_file(args)
        case "check-ignore"       : cmd_check_ignore(args)
        case "checkout"           : cmd_checkout(args) 
        case "commit"             : cmd_commit(args)
        case "hash-object"        : cmd_hash_object(args)
        case "init"               : cmd_init(args)
        case "log"                : cmd_log(args)
        case "ls-files"           : cmd_ls_files(args)
        case "ls-tree"            : cmd_ls_tree(args)
        case "rev-parse"          : cmd_rev_parse(args)
        case "rm"                 : cmd_rm(args)
        case "show-ref"           : cmd_show_ref(args)
        case "status"             : cmd_status(args)
        case "tag"                : cmd_tag(args)
        case _                    : print("Bad command.")




class GitRepository(object):
    """A git repository"""

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a git repository %s" % path)
        
        # read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, 'config')

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("configuration file is missing")
        
        

def repo_create(path):
    """creates a new repository at path"""

    repo = GitRepository(path, True)
    #  first we make sure the path already doesnt exist, or is an empty dir

    if os.path.exists(repo.worktree):
        if not(os.path.isdir(repo.worktree)):
            raise Exception("not a directory %s" % path)
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception("%s is not empty!" % path)
    else:
        os.makedirs(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True )

    # .git/description 
    with open(repo_file(repo, "description"), 'w') as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository. \n")
    
    # .git/HEAD
    with open(repo_file(repo, "HEAD"), 'w') as f:
        f.write("ref: refs/heads/master\n")

    # .git/config
    with open(repo_file(repo, "config"), 'w') as f:
        config = repo_default_config()
        config.write(f)
    
    return repo

def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)
    
    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        # bottom case
        # os.path.join('/', '..') == '/'
        # if parent==path, then path is root
        if required:
            raise Exception("No git directory")
        else:
            return None
    
    return repo_find(parent, required)



def repo_default_config():
    ret = configparser.ConfigParser()
    
    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret

class GitObject(object):

    def __init__(self, data=None):
        if data != None:
            self.deserialize(data)
        else:
            self.init()
    
    def serialize(self, repo):
        """ The function must be implemented by the subclasses. It must read the objects content
        from self.data, a byte string, and do whatever it takes to convert it into a meaningful
        representation. What exactly that means depend on each subclass"""

        raise Exception("Unimplemented")

    def deserialize(self, data):
        raise Exception("Unimplemented")
    
    def init(self):
        pass


def object_read(repo, sha):
    """read object sha from git repository repo. return a GitObject whose exact type
    depends on the object."""

    path = repo_file(repo, "objects", sha[0:2], sha[2:])
    
    if not os.path.isfile(path):
        return None
    
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        #  read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception("malformed object {0}: bad length".format(sha))
        
        match fmt:
            case b'commit' : c=GitCommit
            case b'tree'   : c=GitTree
            case b'tag'    : c=GitTag
            case b'blob'   : c=GitBlob
            case _:
                raise Exception("Unknown type {0} for object {1}".format(fmt.decode("ascii"), sha))
            
        # call constructor and return the object 
        return c(raw[y+1:])

def write_object(obj, repo=None):
    
    # serialize the object data
    data = obj.serialize()
    # add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # compute hash
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        # compute path
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            with open(path, 'wb') as f:
                # compress and write
                f.write(zlib.compress(result))
    return sha


class GitBlob(GitObject):
    fmt=b'blob'
    
    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data


class GitCommit(GitObject):
    fmt = b'commit'

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)
    
    def serialize(self):
        return kvlm_serialize(self.kvlm)
    
    def init(self):
        self.kvlm = dict()






# utility
def repo_path(repo, *path):
    """Compute path under repo's gitdir"""
    return os.path.join(repo.gitdir, *path)


def repo_file(repo, *path, mkdir=False):
    """ same as repo_path, but creates dirname(*path) if absent. For example, repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\")
    will create .git/refs/remote/origin.
    """
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)


def repo_dir(repo, *path, mkdir=False):
    """same as repo_path, but mkdir *path if absent if mkdir"""

    path = repo_path(repo, *path)

    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception("Not a directory %s" % path)
        
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None


def kvlm_parse(raw, start=0, dct=None):
    if not dct:
        dct = collections.OrderedDict()
        #  you cannot declare the argument as dct=OrderedDict() or all the calls to the functions
        # will endlessly grow the same dict.

    # this function is recursive: it reads a key/value pair, then call itself back with a new position. So we
    # first need to know where we are: at a keyword, or already in the messageQ

    # we search for the next space and the next newline
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)


    # if space appears before newline, we have a keyword. Otherwise, it's the final message, which we just read to 
    # the end of the file.
    
    # Base case
    # =========
    # if newline appears first (or there's no space at all, in which case returns -1), we assume a blank line. A blank line
    # means the remainder of the data is the message. We store it in the dictionary, with None as the key, and return.
    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start+1:]
        return dct

    # Recursive case:
    # ===============
    # we read a key-value pair and recurse for the next
    key = raw[start:spc]

    # find the end of the value. Continuation lines begin with a space, so we loop until we find a "\n" not followed by a space.
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end + 1] != ord(' '): break 
    
    # grab the value
    # also, drop the leading space on continuation lines
    value = raw[spc+1:end].replace(b'\n ', b'\n' )

    # dont overwrite existing data content
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)

        else:
            dct[key] = [dct[key], value]
    
    else:
        dct[key] = value

    
    return kvlm_parse(raw, start=end+1, dct=dct)


def kvlm_serialize(kvlm):
    ret = b''

    # output fields
    for k in kvlm.keys():
        # skip the message itself
        if k == None: continue
        val = kvlm[k]
        # normalize to a list
        if type(val) != list:
            val = [val]

        for v in val:
            ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'
    
    # append the message
    ret += b'\n' + kvlm[None] + b'\n'

    return ret

