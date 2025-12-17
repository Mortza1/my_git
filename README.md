# wyag - Write Yourself A Git

An educational implementation of Git's core functionality in Python, created to understand how version control systems work at a fundamental level.

## About

This project is a recreation of Git to better understand its internal workings. It follows the excellent tutorial **"Write yourself a Git!"** by Thibault Polge, available at https://wyag.thb.lt/

The implementation provides a simplified but functional version control system that demonstrates Git's core concepts: content-addressed storage, object model, tree structures, and commit history.

## How Git Works (Under the Hood)

Git is fundamentally a **content-addressed filesystem** with a version control interface on top. This implementation recreates the essential mechanisms:

### Content-Addressed Storage
- Every file and piece of metadata is stored as an **object** identified by its SHA-1 hash
- Objects are compressed with zlib and stored in `.git/objects/`
- The hash is computed from the object's content, making it immutable
- Same content always produces the same hash (deduplication)

### The Four Object Types

1. **Blob** - Stores file contents
   - Raw file data without any metadata
   - Just the content, nothing else

2. **Tree** - Stores directory structure
   - Lists of files and subdirectories
   - Each entry has: mode (permissions), type, SHA-1 hash, filename
   - Represents a snapshot of the filesystem at a point in time

3. **Commit** - Stores commit metadata
   - References a tree (filesystem snapshot)
   - References parent commit(s) (history)
   - Contains author, committer, timestamp, message
   - Forms a directed acyclic graph (DAG) of project history

4. **Tag** - Stores annotated tag information
   - Named reference to another object
   - Can include tagger info and message

### Repository Structure

```
.git/
├── objects/          # All Git objects (blobs, trees, commits, tags)
│   ├── 01/          # Objects are sharded by first 2 hex digits
│   ├── 02/
│   └── ...
├── refs/
│   ├── heads/        # Branch references (pointers to commits)
│   └── tags/         # Tag references
├── HEAD              # Points to current branch
├── config            # Repository configuration
└── description       # Repository description
```

## Implementation Details

### Architecture

The implementation consists of two main files:

- **`wyag`** - Entry point script that calls the main function
- **`libwyag.py`** - Core library (605 lines) containing:
  - Command-line interface with argparse
  - Repository management (`GitRepository` class)
  - Object model (GitBlob, GitCommit, GitTree, GitTag classes)
  - Serialization/deserialization routines
  - Object storage and retrieval
  - Tree traversal and checkout logic

### Key Components

#### Repository Management
- `GitRepository` class manages the repository structure
- `repo_create()` initializes a new repository with proper directory structure
- `repo_find()` locates a repository by searching parent directories
- Configuration parsing using Python's `configparser`

#### Object Handling
- `object_read()` - Loads and deserializes objects from storage
- `object_write()` - Serializes, hashes, and stores objects
- `object_hash()` - Computes SHA-1 hash and creates objects from files
- Each object type implements `serialize()` and `deserialize()` methods

#### Data Structures
- **KVLM** (Key-Value List with Message) - Format for commits and tags
  - Ordered dictionary of key-value pairs
  - Supports multiple values for same key (e.g., multiple parents)
  - Message starts after first blank line
- **Tree parsing** - Binary format with variable-length entries
  - Each entry: mode (ASCII), space, path (null-terminated), SHA-1 (20 bytes)

## Implemented Commands

### `init [path]`
Initialize a new Git repository.

```bash
./wyag init myrepo
```

Creates the `.git` directory structure with all necessary subdirectories and config files.

### `hash-object [-w] [-t TYPE] FILE`
Compute object hash and optionally store it.

```bash
./wyag hash-object myfile.txt              # Just compute hash
./wyag hash-object -w myfile.txt          # Hash and write to repo
./wyag hash-object -w -t blob myfile.txt  # Explicitly specify type
```

Options:
- `-w` - Write the object to the repository
- `-t TYPE` - Specify object type (blob, commit, tree, tag)

### `cat-file TYPE OBJECT`
Display the contents of a repository object.

```bash
./wyag cat-file blob 1a2b3c4d
./wyag cat-file commit HEAD
./wyag cat-file tree abc123
```

Retrieves the object by its SHA-1 hash and displays its deserialized content.

### `log COMMIT`
Display commit history as a graph.

```bash
./wyag log HEAD > commits.dot
dot -O -Tpng commits.dot  # Generate PNG with Graphviz
```

Outputs the commit history in Graphviz DOT format, showing the commit DAG with parent relationships.

### `ls-tree [-r] TREE`
List the contents of a tree object.

```bash
./wyag ls-tree HEAD               # List root tree of HEAD commit
./wyag ls-tree -r abc123          # Recursively list all files
```

Options:
- `-r` - Recursively list subdirectories

Output format:
```
[mode] [type] [hash]    [path]
100644 blob  a1b2c3d4... file.txt
040000 tree  e5f6g7h8... src/
```

### `checkout COMMIT PATH`
Restore files from a commit to a directory.

```bash
./wyag checkout HEAD ./output
./wyag checkout abc123def456 ./my-dir
```

Recreates the entire directory structure and files from the specified commit.

## How It Works: Example Workflow

### 1. Initialize Repository
```bash
./wyag init myproject
cd myproject
```

Creates `.git/` with all necessary structure.

### 2. Hash Objects
```bash
echo "Hello, Git!" > hello.txt
./wyag hash-object -w hello.txt
# Output: 8ab686eafeb1f44702738c8b0f24f2567c36da6d
```

The file content is:
1. Prefixed with header: `blob 12\0` (type, space, size, null byte)
2. SHA-1 hashed: `8ab686...`
3. Compressed with zlib
4. Stored in `.git/objects/8a/b686eafeb1f44702738c8b0f24f2567c36da6d`

### 3. View Objects
```bash
./wyag cat-file blob 8ab686eafeb1f44702738c8b0f24f2567c36da6d
# Output: Hello, Git!
```

Reads the object file, decompresses it, verifies the type, and displays content.

### 4. Work with Trees and Commits
Trees and commits can be read from existing repositories:

```bash
./wyag ls-tree HEAD              # List files in HEAD commit
./wyag log HEAD > history.dot    # Export commit history
./wyag checkout abc123 ./restore # Restore entire commit
```

## Technical Details

### SHA-1 Hashing
- Uses Python's `hashlib.sha1()`
- Hash is computed from: header + content
- Header format: `{type} {size}\0`
- Example: `blob 12\0Hello, Git!` → SHA-1 hash

### Compression
- All objects stored compressed with zlib
- Reduces storage space significantly
- Transparent decompression on read

### Object Storage
- Objects stored in `.git/objects/{first-2-hex}/{remaining-38-hex}`
- Example: hash `8ab686ea...` → `.git/objects/8a/b686ea...`
- Sharding by first 2 characters improves filesystem performance

### Tree Format (Binary)
Each tree entry:
```
[mode] [path]\0[20-byte-sha1][mode] [path]\0[20-byte-sha1]...
```

Modes (file permissions):
- `100644` - Regular file
- `100755` - Executable file
- `040000` - Directory (tree)
- `120000` - Symbolic link

### Commit Format (KVLM)
```
tree [sha1]
parent [sha1]
author [name] <[email]> [timestamp] [timezone]
committer [name] <[email]> [timestamp] [timezone]

[commit message]
```

## Requirements

- Python 3.10+ (uses match statements)
- Standard library modules:
  - `argparse` - CLI parsing
  - `collections` - OrderedDict
  - `configparser` - Config file handling
  - `hashlib` - SHA-1 hashing
  - `zlib` - Compression
  - `os`, `sys`, `re` - System utilities

Optional:
- Graphviz - For rendering commit history graphs

## Installation & Usage

```bash
# Clone the repository
git clone <your-repo-url>
cd my_git

# Make wyag executable
chmod +x wyag

# Run commands
./wyag init test-repo
./wyag hash-object -w somefile.txt
./wyag cat-file blob <hash>
```

## Project Status

This implementation covers the fundamental Git operations:
- ✅ Repository initialization
- ✅ Object storage and retrieval
- ✅ Blob handling
- ✅ Tree parsing and serialization
- ✅ Commit reading and history
- ✅ Checkout functionality
- ✅ Tree listing

Not implemented (standard Git features):
- Creating commits
- Branch management
- Merging
- Remote operations (push/pull/fetch)
- Index/staging area
- Diff generation
- Many other Git commands

## Learning Resources

This project is based on:
- **"Write yourself a Git!"** tutorial by Thibault Polge: https://wyag.thb.lt/
- Git internals documentation: https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain
- Git source code: https://github.com/git/git

## Educational Value

By implementing Git from scratch, you learn:
- How content-addressed storage works
- The beauty of Git's simple object model
- How commits form a directed acyclic graph
- Why Git is so fast (hashing, compression, deduplication)
- The difference between Git's internal "plumbing" and user-facing "porcelain" commands
- How version control systems work at a fundamental level

## License

This is an educational project following the tutorial at https://wyag.thb.lt/

Original tutorial by Thibault Polge. Implementation by the tutorial followers.

## Contributing

This is a learning project. Feel free to:
- Experiment with the code
- Add new commands
- Improve documentation
- Share your understanding

---

*"The stupidest content tracker"* - Git's original description, fitting for this educational implementation!
