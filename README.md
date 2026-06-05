# GSB Canvas Archive

Download all your Stanford GSB Canvas course materials — slides, readings, and assignments — to your computer, then search everything using Claude AI.

**No coding experience needed.** Just follow the steps below.

---

## What this does

This tool logs into Canvas as you, downloads all your course files, and organizes them into folders on your computer. You can then upload everything to Google Drive and ask Claude questions like *"What the customer discovery frameworks from Startup Garage?"* or *"Based on everything I learned at GSB — coursework, guest speakers, cases — what are the most important signals VCs look for when evaluating early-stage founders?."*

It downloads:
- 📁 Slides and readings from every module
- 📝 Assignment descriptions, your submissions, and instructor feedback
- 🗂 Course syllabi and home pages

---

## Before you start

You need two things installed on your computer. This is a one-time setup.

### Step 1 — Install Python

1. Go to **[python.org/downloads](https://www.python.org/downloads/)** and download the latest version.
2. Run the installer.
   - **Windows:** On the first screen, check the box that says **"Add Python to PATH"** before clicking Install. This is easy to miss.
   - **Mac:** Follow the default prompts.
3. To confirm it worked, open a terminal and run:
   ```
   python --version
   ```
   You should see something like `Python 3.12.0`. Any version 3.10 or higher is fine.

> **How to open a terminal:**
> - **Windows:** Press `Win + R`, type `powershell`, press Enter.
> - **Mac:** Press `Cmd + Space`, type `Terminal`, press Enter.

### Step 2 — Download this tool

1. Click the green **Code** button at the top of this page.
2. Click **Download ZIP**.
3. Unzip the downloaded file. Move the `gsb-archive` folder somewhere easy to find, like your Desktop.

---

## Get your Canvas token

Your Canvas token is like a password that lets this tool download your own course materials. It can only see **your** courses — not anyone else's.

1. Go to **[canvas.stanford.edu](https://canvas.stanford.edu)** and sign in.
2. Click your **profile picture** in the top-left corner → **Settings**.
3. Scroll down to **Approved Integrations**.
4. Click **+ New Access Token**.
5. In the **Purpose** field, type anything — e.g. `GSB Archive`.
6. Leave **Expires** blank.
7. Click **Generate Token**.
8. A long string of letters and numbers appears. **Copy it now** — Canvas will never show it again.

> ⚠️ **Keep this token private.** Do not paste it into a chat, email, or shared doc. It goes only into the private config file below.
>
> If you ever share it by accident, go back to Canvas Settings → Approved Integrations, find the token, and click **Delete** to immediately cancel it. Then generate a new one.

---

## Set up the tool

Open a terminal and navigate to the folder you downloaded. The easiest way:

**Windows:**
1. Open File Explorer and find the `gsb-archive` folder.
2. Click in the address bar at the top, type `powershell`, and press Enter. A terminal opens already in the right place.

**Mac:**
1. Open Terminal.
2. Type `cd ` (with a space after), then drag the `gsb-archive` folder from Finder into the Terminal window. Press Enter.

Now run these commands **one at a time**, pressing Enter after each:

**1. Create an isolated workspace for the tool:**
```
python -m venv .venv
```

**2. Activate the workspace:**

Windows:
```
.venv\Scripts\Activate.ps1
```

Mac:
```
source .venv/bin/activate
```

> If you get a permissions error on Windows, run this first, then try again:
> ```
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**3. Install the tool's dependencies:**
```
pip install -r requirements.txt
```
This downloads a few libraries the tool needs. It may take a minute.

**4. Create your config file:**

Windows:
```
Copy-Item .env.example .env
```

Mac:
```
cp .env.example .env
```

**5. Add your Canvas token to the config file:**

Open the `.env` file in any text editor (Notepad on Windows, TextEdit on Mac). It looks like this:

```
CANVAS_TOKEN=
CANVAS_BASE_URL=https://canvas.stanford.edu
```

Paste your token after the `=` on the first line so it looks like:

```
CANVAS_TOKEN=your_long_token_here
CANVAS_BASE_URL=https://canvas.stanford.edu
```

Save and close the file.

> **.env files are hidden by default.** If you can't see it in File Explorer or Finder, that's normal — the tool can still read it. You can also open it from the terminal with `notepad .env` (Windows) or `open -e .env` (Mac).

**6. Test that everything is working:**
```
python -m canvas_export verify
```

You should see a small table with your name and Stanford email. If you get an error, double-check that your token was copied fully with no extra spaces.

---

## Download your courses

Run these steps in order. Each one is safe to re-run if something goes wrong — it skips files already downloaded.

---

### Phase 1 — Find your courses

```
python -m canvas_export discover
```

This finds all your Canvas courses and lists them. **By default, each course is filed into a folder named after its Canvas term** (e.g. `Spring 2024`, `Fall 2024`) — so you don't have to do anything to organize them. You can skip straight to Phase 2.

#### (Optional) Organize and trim your courses

If you'd rather group courses by topic, or skip a few you don't want, run:

```
python -m canvas_export categorize
```

This shows you every course that will be downloaded and the folder it will go into. It then asks if you want to adjust anything. If you say yes, it walks through your courses **one at a time, right in the terminal** — no spreadsheet to open. For each course you can:

- **Type a topic name** (e.g. `AI and Programming`, `Finance and Econ`) to file it under that folder instead of the term — great for grouping related courses across quarters.
- **Press Enter** to keep it where it is.
- **Type `-`** to reset it back to its Canvas term.
- **Type `x`** to exclude it from the archive entirely — good for orientation modules, empty placeholders, or courses from other schools.
- **Type `q`** to stop and save at any point.

You can re-run `categorize` as many times as you like; it remembers your previous choices.

**Before moving on:** run a dry run to preview the folder structure:

```
python -m canvas_export files --dry-run
```

This prints what folders would be created without downloading anything. If something looks off, re-run `categorize` and adjust.

---

### Phase 2 — Download course files

```
python -m canvas_export files
```

Downloads all slides, readings, and files from every module. Large courses take a few minutes each. You'll see progress bars while it runs.

---

### Phase 3 — Download assignments

```
python -m canvas_export assignments
```

Downloads every assignment with your submission and any instructor comments. Saves them as PDFs (or as HTML files you can open in your browser if PDF conversion isn't available on your machine).

---

## Upload to Google Drive

Once downloading is complete, upload your files to Google Drive so Claude can search them.

### Install Google Drive for Desktop

1. Download **[Google Drive for Desktop](https://www.google.com/drive/download/)** and install it.
2. Sign in with your **personal** Google account (not your Stanford account, unless you prefer that).
3. When prompted, choose **"Mirror files"** so a copy stays on your computer.

### Copy your files into Drive

1. Find the folder that Google Drive created on your computer:
   - **Windows:** Open File Explorer — it appears as `Google Drive (G:)` or similar in the left sidebar.
   - **Mac:** Open Finder — it appears under Locations.
2. Open `My Drive` inside it.
3. Create a new folder called **`Stanford Canvas Archive`**.
4. Open your `gsb-archive` folder, go into the `downloads` folder, and copy everything inside into `Stanford Canvas Archive`.
5. The sync starts automatically. The Google Drive icon in your taskbar/menu bar shows a spinner while uploading — wait for it to show a checkmark.

> For large archives this can take 30–60 minutes depending on your internet speed. You can leave it running in the background.

---

## Search your archive with Claude

Once your files are in Google Drive, set up a Claude Project to search them.

### Step 1 — Create a project

1. Go to **[claude.ai](https://claude.ai)** and sign in.
2. In the left sidebar, click **Projects** → **New Project**.
3. Name it something like `Stanford GSB Coursework`.

### Step 2 — Add your instructions

Click **Edit project instructions** and paste this exactly:

```
When I ask questions about my GSB coursework, search my Google Drive folder "Stanford Canvas Archive" for relevant materials. Cite the specific course and file where possible. If a query is ambiguous about scope, default to searching that folder.
```

### Step 3 — Connect Google Drive

1. Inside the project, click **Add content** (or the `+` button).
2. Select **Google Drive**.
3. Authorize Claude to access your Google account if prompted.
4. Navigate to and select the **`Stanford Canvas Archive`** folder.
5. Click **Add**. Claude will index the files — this takes a few minutes.

### Step 4 — Start asking questions

Once indexed, open a chat inside the project and try things like:

- *"What were the main frameworks covered in my strategy courses?"*
- *"Find any reading that discusses cap table dilution."*
- *"What feedback did I get on my FINANCE 321 final assignment?"*
- *"Summarize what I learned about negotiation across all my courses."*

Claude will search the archive and cite the specific course and file.

---

## Something went wrong?

**"CANVAS_TOKEN is not set"**
The `.env` file is missing or in the wrong folder. Make sure it's inside `gsb-archive/`, next to `requirements.txt`. Open it and confirm your token is pasted after the `=` with no spaces.

**The terminal says "python is not recognized" or "command not found"**
Python wasn't added to your PATH during installation. On Windows, re-run the Python installer, click "Modify", and check the "Add Python to environment variables" box.

**Assignments saved as `.html` instead of `.pdf`**
Your computer is missing a library that converts to PDF. The `.html` files are identical in content — just open them in any web browser (Chrome, Safari, etc.).

**A file failed to download**
The tool skips it and keeps going. Check `logs/errors.log` for details. Common cause: the instructor restricted access after the term ended. Re-running `files` or `assignments` will retry missing files.

**Google Drive is still syncing / spinner won't stop**
Very large files (videos embedded in pages, large PDFs) take longer. Give it time. If it's stuck after several hours, try pausing and resuming sync from the Drive for Desktop menu.

**Claude says it can't find something**
Check that the file finished syncing in Google Drive (no spinner icon next to it). New files can take up to an hour to be indexed after they appear in Drive. If it's still missing, try removing and re-adding the folder in your Claude Project settings.

---

## Privacy

- Your Canvas token only accesses your own courses. Never share it.
- Your downloaded files, token, and course list never leave your computer unless you upload them to Drive yourself.
- The `downloads/`, `manifests/`, and `logs/` folders — and the `.env` file — are excluded from this repository and will never be uploaded to GitHub.
