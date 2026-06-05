# GSB Canvas Archive

A Python CLI that downloads your Stanford GSB Canvas course materials to your
local machine — slides, readings, assignment descriptions, and your submitted
work — then lets you search everything with Claude AI via Google Drive.

Runs on Windows, macOS, and Linux. Safe to re-run; it skips anything already
downloaded.

---

## What it archives

| Phase | Command | What you get |
|-------|---------|-------------|
| 1 | `discover` | A CSV listing all your Canvas courses |
| 2 | `files` | Slides, readings, and all files embedded in course pages |
| 3 | `assignments` | Assignment descriptions + your submissions, rendered to PDF |

---

## Prerequisites

### 1. Python 3.10 or later

Check by running:

```
python --version
```

Download from [python.org](https://www.python.org/downloads/) if needed.
During install on Windows, tick **"Add Python to PATH"**.

### 2. WeasyPrint system dependency (optional — for PDF output)

WeasyPrint converts assignment pages to PDF. Without it, assignments are saved
as `.html` files instead — same content, just open in your browser.

- **macOS:** `brew install pango`
- **Windows:** Install the
  [GTK3 runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)
  (run the `.exe`, default settings are fine), then restart your terminal.
- **Linux (Debian/Ubuntu):** `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`

The tool prints a clear message at startup if WeasyPrint is unavailable and
falls back to HTML automatically — you will not lose any content.

---

## Installation

**1. Get the code**

Unzip the project folder somewhere on your machine (e.g. your Desktop).
Open a terminal and navigate into it:

```
cd path/to/gsb-archive
```

**2. Create a virtual environment**

```
python -m venv .venv
```

**3. Activate it**

macOS / Linux:
```
source .venv/bin/activate
```

Windows (PowerShell):
```
.venv\Scripts\Activate.ps1
```

Windows (Command Prompt):
```
.venv\Scripts\activate.bat
```

Your prompt should now show `(.venv)`.

**4. Install dependencies**

```
pip install -r requirements.txt
```

---

## Get your Canvas token

### What is it?

A Canvas personal access token is a password-like key that lets this tool log
into Canvas as you and download your own course materials. It can only see your
data — Canvas does not allow one student's token to access another student's
courses or submissions.

### How to generate one

1. Go to **canvas.stanford.edu** and sign in with your SUNet ID.
2. Click your profile picture (top-left corner) → **Settings**.
3. Scroll down to the **Approved Integrations** section.
4. Click **+ New Access Token**.
5. In the **Purpose** field, type something like `GSB Archive`.
6. Leave the **Expires** field blank (no expiry).
7. Click **Generate Token**.
8. A long string of letters and numbers appears — **copy it now**.
   Canvas will never show it to you again.

### Keep it safe

- **Do not share your token** with anyone, including classmates.
- **Do not paste it into a chat, email, or shared document.**
- It goes only into your local `.env` file (see Configure below), which is
  excluded from any file-sharing by `.gitignore`.
- If you ever suspect your token was exposed, go back to Canvas Settings →
  Approved Integrations, find the token, and click **Delete** to revoke it
  immediately. Then generate a new one.

---

## Configure

Copy the example env file:

```
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Open `.env` in any text editor (Notepad is fine) and paste your token:

```
CANVAS_TOKEN=paste_your_token_here
CANVAS_BASE_URL=https://canvas.stanford.edu
```

Save and close. This file never leaves your machine.

---

## Test your setup

```
python -m canvas_export verify
```

You should see a small table showing your name and Stanford email. If you see
an error, re-check that the token in `.env` was copied completely with no
extra spaces.

---

## Running the archive

Run these steps in order. Every step is safe to re-run — it skips work that
is already done.

---

### Step 1 — Discover your courses

```
python -m canvas_export discover
```

This creates `course_inventory.csv` with every Canvas course you are enrolled
in. Open it in Excel or Google Sheets.

**You need to do two things before continuing:**

#### A. Mark courses to skip

Set the `include` column to `FALSE` for any course you do not want to
archive. Common candidates: orientation modules, bootcamps, cross-registration
courses from other schools, placeholder shells with no content.

Leave everything else as `TRUE`.

#### B. Choose how to organize your folders

The `category` column controls your top-level folder structure inside
`downloads/`. Decide which approach works better for you, then fill in the
column accordingly.

---

**Option 1 — Organize by topic** *(recommended if you want to find related
material across quarters in one place)*

Fill in the `category` column with a subject label for each course. Examples:

| category |
|----------|
| AI and Programming |
| Finance and Econ |
| Leadership and Soft Skills |
| Startup and VC |
| Career and Life |

You can use any labels you like — they become folder names.

---

**Option 2 — Organize by term** *(simpler; mirrors Canvas's own structure)*

The `term` column is already filled in for you (e.g., `Spring 2024`,
`Fall 2024`). To use it as your folder structure, copy each course's `term`
value into its `category` column.

In Excel you can do this for all rows at once:
1. Click the first empty cell in the `category` column (the one next to
   your first course row).
2. Type `=` and then click the corresponding cell in the `term` column.
   Press Enter.
3. Copy that formula down to all other course rows.
4. Select all the `category` cells you just filled → Copy → Paste Special →
   **Values only** (so the column contains plain text, not formulas).

---

**Verify your categories before downloading**

Once the CSV is saved, do a dry run to preview exactly which folders will be
created — no files are downloaded:

```
python -m canvas_export files --dry-run
```

Review the printed list. If anything looks wrong (wrong category, a course
that should be excluded), go back and edit the CSV, then run `--dry-run`
again until it looks right.

> If you want to re-categorize after already downloading files, you can
> edit `course_inventory.csv` and re-run `discover` at any time — it
> preserves your `include` and `category` edits. Then re-run `files` and
> only the folder structure changes; existing files are not re-downloaded.

---

### Step 2 — Download course files

```
python -m canvas_export files
```

Downloads slides, readings, and all files embedded in course pages. Large
courses can take a few minutes each. Progress bars show per-module status.

To test on a single course before running everything:

```
python -m canvas_export files --course-id COURSE_ID
```

Replace `COURSE_ID` with the numeric ID from `course_inventory.csv`.

---

### Step 3 — Archive assignments

```
python -m canvas_export assignments
```

Downloads every assignment description along with your submission and any
instructor comments. Saves as PDF (or HTML if WeasyPrint is unavailable).

---

## Output layout

```
downloads/
  [category]/
    [course code] - [course name]/
      [NN] - [module name]/
        file.pdf
        page-title.html
        link-title.url        <- external links saved as browser shortcuts
      _assignments/
        01 Assignment Name.pdf
      _Syllabus.html
      _Home - Page Title.html
logs/
  errors.log                  <- per-file errors (skips, not crashes)
manifests/
  [course_id].json            <- tracks what has been downloaded
```

---

## Upload to Google Drive

Once the download is complete, upload your `downloads/` folder to Google Drive
so you can search it with Claude (next section).

**Recommended: use Google Drive for Desktop**

Google Drive for Desktop syncs a folder on your computer to your Drive
automatically. This is the easiest way to upload a large number of files.

1. Download and install **Google Drive for Desktop**:
   [drive.google.com/drive/download](https://www.google.com/drive/download/)

2. Sign in with your personal Google account (not your Stanford account, unless
   you want to use that).

3. After installation, open Google Drive for Desktop preferences and choose
   **"Mirror files"** so a local copy stays on your machine.

4. Find the folder that Google Drive synced to your computer:
   - **Windows:** `G:\My Drive\` (Drive appears as a drive letter)
   - **macOS:** `~/Google Drive/My Drive/`

5. Create a new folder inside `My Drive` called **`Stanford Canvas Archive`**.

6. Copy (or move) the entire contents of your `downloads/` folder into
   `Stanford Canvas Archive`. The sync will begin automatically.

7. Wait for the sync to finish — the Drive for Desktop icon in your system
   tray shows a spinner while it's working, and a checkmark when done.

> **Alternative (no install required):** Go to
> [drive.google.com](https://drive.google.com), create a folder called
> `Stanford Canvas Archive`, and drag your `downloads/` subfolders into it
> from File Explorer / Finder. This works fine but is slower for large uploads.

---

## Set up Claude to search your archive

Once your files are in Google Drive, you can set up a Claude Project that
searches them whenever you ask questions about your coursework.

### 1. Create a new Project

1. Go to [claude.ai](https://claude.ai) and sign in.
2. In the left sidebar, click **Projects** → **New Project**.
3. Give it a name, e.g. `Stanford GSB Coursework`.

### 2. Add your Project Instructions

Click **Edit project instructions** and paste the following exactly:

```
When I ask questions about my GSB coursework, search my Google Drive folder
"Stanford Canvas Archive" for relevant materials. Cite the specific course
and file where possible. If a query is ambiguous about scope, default to
searching that folder.
```

### 3. Connect Google Drive

1. Inside the project, click **Add content** (or the `+` button near the
   knowledge section).
2. Choose **Google Drive**.
3. Authorize Claude to access your Google account if prompted.
4. Navigate to and select the **`Stanford Canvas Archive`** folder.
5. Click **Add** — Claude will index the files.

Indexing may take a few minutes depending on how many files you uploaded.
Once done, you can ask questions like:

- *"What were the main frameworks covered in my strategy courses?"*
- *"Find any reading that discusses cap table dilution."*
- *"What was my submission for the FINANCE 321 final assignment?"*

Claude will search the archive and cite the specific course and file in its
answer.

---

## Troubleshooting

**"CANVAS_TOKEN is not set"**
You have not created `.env` or it is in the wrong folder. Make sure `.env`
sits inside the `gsb-archive/` folder, next to `requirements.txt`.

**"Course X not in inventory (or include=FALSE)"**
Either the course ID does not exist in `course_inventory.csv`, or you set
its `include` column to `FALSE`. Run `discover` again if you recently gained
access to a course.

**Assignments save as `.html` instead of `.pdf`**
WeasyPrint is not installed or its system dependency is missing. See the
WeasyPrint section above. HTML files open in any browser and contain all
the same content.

**A file fails to download**
The tool logs the error and moves on. Check `logs/errors.log` for details.
Common causes: the file was restricted by the instructor after the term ended,
or a temporary network error. Re-running the phase retries only the missing
files.

**Permission error activating the venv on Windows**
Run this once in PowerShell (as your regular user, not admin):
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Claude can't find a file I know was downloaded**
Check that the file synced fully to Google Drive (no spinner icon next to it
in Drive for Desktop). Very large PDFs can take a few minutes to index after
syncing. If it still doesn't appear after an hour, try removing and re-adding
the folder in your Claude Project.

---

## Privacy notes

- Your Canvas token accesses your courses only. Never share it.
- `.env`, `downloads/`, `manifests/`, `logs/`, `token.json`, and
  `credentials.json` are all listed in `.gitignore` — they are excluded if
  you share the project folder with anyone.
- `course_inventory.csv` is generated from your own Canvas account and
  contains your course list. Do not share your copy.
- Files uploaded to Google Drive are subject to Google's privacy policy.
  Use your personal account and keep the folder private (the default).
