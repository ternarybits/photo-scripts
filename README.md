# Photo Scripts

Scripts for managing duplicate photos - renaming files with duplicate names and finding/removing duplicate content.

## Prerequisites for Non-Technical Users

### Step 1: Install Homebrew (Mac only)
If you're on a Mac and don't have Homebrew installed, open Terminal and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the instructions that appear after installation completes.

### Step 2: Install Python
The scripts require Python 3.9 or newer.

**On Mac:**
```bash
brew install python@3.13
```

**On Windows:**
Download and install Python from https://www.python.org/downloads/
- During installation, make sure to check "Add Python to PATH"

**On Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip
```

### Step 3: Install uv (Python package manager)
Open Terminal (Mac/Linux) or Command Prompt (Windows) and run:

```bash
# On Mac/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (in PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal.

## Installation

Once you have the prerequisites installed:

1. **Download the scripts:**
   - Click the green "Code" button on GitHub and select "Download ZIP"
   - Extract the ZIP file to a folder on your computer
   - Or if you're familiar with git: `git clone <repository-url>`

2. **Open Terminal/Command Prompt:**
   - Mac: Press Cmd+Space, type "Terminal", press Enter
   - Windows: Press Windows key, type "cmd", press Enter
   - Navigate to the folder: `cd /path/to/photo-scripts`

3. **Install the scripts:**
   ```bash
   # This installs all necessary components
   uv sync
   ```

## How to Use the Scripts

### Understanding the Modes
Both scripts have two modes:
- **list**: Shows you what WOULD happen without making any changes (safe to try!)
- **run**: Actually performs the changes

Always use `list` mode first to preview the changes!

### Script 1: rename-duplicates

This script finds files with the same name in different folders and renames them to be unique.

**Basic usage:**
```bash
# First, see what files would be renamed (safe - no changes made)
uv run rename-duplicates list /path/to/photos /path/to/more/photos

# If you're happy with the preview, apply the changes
uv run rename-duplicates run /path/to/photos /path/to/more/photos
```

**Real example:**
```bash
uv run rename_duplicates.py list demo/photos1 demo/photos2
Scanning 2 directories for duplicate filenames...

  Scanning directories... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

Scanned 4 files
Found 1 filenames with duplicates

Found 1 files to rename

                                Planned Rename Operations                                
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Original Path             ┃ New Path                    ┃ Reason                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ demo/photos2/vacation.jpg │ demo/photos2/vacation-1.jpg │ Duplicate of 'vacation.jpg' │
└───────────────────────────┴─────────────────────────────┴─────────────────────────────┘

Summary:
Mode: list
Execution time: 0.10s
Total files to rename: 1
Duplicate filename groups: 1
```

Features:
- Scans directories recursively
- Adds numerical suffixes to make filenames unique (e.g., `photo.jpg` → `photo-1.jpg`, `photo-2.jpg`)
- Shows progress with detailed statistics
- Parallel processing for better performance

### Script 2: deduplicate-photos

This script finds files that have identical content (even if they have different names) and moves the duplicates to a separate folder.

**Basic usage:**
```bash
# First, see what duplicates would be moved (safe - no changes made)
uv run deduplicate-photos list /path/to/photos /path/to/more/photos

# If you're happy with the preview, move the duplicates
uv run deduplicate-photos run /path/to/photos /path/to/more/photos

# Choose where to put duplicates (default is a folder called "duplicates")
uv run deduplicate-photos run /path/to/photos --duplicates-directory /path/to/my-duplicates
```

**Real example:**
```bash
uv run deduplicate-photos list demo/photos1 demo/photos2
Scanning 2 directories for duplicate files...

⠋ Discovering files...
Found 4 files to process

  Calculating file hashes... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Found 1 size groups with potential duplicates

  Finding duplicates... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

Found 1 groups of duplicate files

                                    Duplicate Files Found                                     
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Keep                              ┃ Remove                    ┃ Size    ┃ Hash             ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ demo/photos1/subdir/duplicate.jpg │ demo/photos1/vacation.jpg │ 0.00 MB │ 2eba901e088d5a8… │
└───────────────────────────────────┴───────────────────────────┴─────────┴──────────────────┘

Summary:
Mode: list
Execution time: 0.11s
Duplicate groups found: 1
Total duplicate files: 1
Space that can be saved: 0.00 GB
```

Features:
- Smart hashing algorithm (partial hash first, full hash only when needed)
- Parallel processing for faster duplicate detection
- Keeps the first occurrence, moves the rest
- Shows progress and summary statistics including space saved


## Tips for Non-Technical Users

### Before You Start
1. Always use `list` mode first to preview what will happen
2. Start with a small test folder to get comfortable with the scripts

### Common Scenarios

**Scenario 1: "I have photos from my phone and camera with the same names"**
```bash
# This will rename files like IMG_1234.jpg to IMG_1234-1.jpg, IMG_1234-2.jpg, etc.
uv run rename-duplicates list ~/Pictures/iPhone ~/Pictures/Camera
```

**Scenario 2: "I accidentally copied my photos multiple times"**
```bash
# This will find exact duplicates and move extras to a 'duplicates' folder
uv run deduplicate-photos list ~/Pictures
```

### Understanding the Output
- **Green text**: Good news or successful operations
- **Yellow text**: Information or things to review
- **Red text**: Errors or failed operations
- The progress bar shows how much work is done
- The summary at the end tells you exactly what happened

## Troubleshooting

### "Command not found" errors
- Make sure you're in the photo-scripts folder: `cd /path/to/photo-scripts`
- Make sure you ran `uv sync` after downloading the scripts

### "Permission denied" errors
- On Mac/Linux, you might need to make the scripts executable:
  ```bash
  chmod +x rename_duplicates.py deduplicate_photos.py
  ```

### The scripts seem slow
- The scripts are optimized for accuracy over speed
- For very large collections (10,000+ files), the first scan might take a few minutes
- The progress bar will show you how long it will take

### "No duplicates found" but you know there are duplicates
- For rename-duplicates: Only finds files with exactly the same name
- For deduplicate-photos: Only finds files with exactly the same content
- Make sure you're checking the right directories

## Development

```bash
# Run tests
uv run pytest

# Run linting
uv run ruff check --fix

# Format code
uv run ruff format

# Type checking
uv run pyright
```

## Performance

Both scripts use parallel processing to handle large photo collections efficiently:
- Multi-threaded directory scanning
- Parallel file hashing with smart partial hashing for large files
- Progress bars show current status and estimated time remaining