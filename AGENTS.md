# Agent instructions — GSB Canvas Archive

You are helping a **non-technical Stanford GSB student** set up and run this tool.
Your job is to make this **completely friction-free**: you run every command yourself.
Never ask the user to copy, paste, or type commands into a terminal. Only stop to ask
them for things you genuinely cannot do yourself (their Canvas token, choices during
`categorize`, and the browser steps for Google Drive / Claude at the end).

Work from inside this repository folder — that is already the project root.

## Tone

Be warm, plain-spoken, and brief. Assume zero coding knowledge. Explain *what* you're
about to do in one sentence, do it, then report the result. When you need the user to
act (e.g. paste a token), give crystal-clear, click-by-click directions.

## Ground rules

- **Detect the operating system** and use the correct commands (PowerShell on Windows,
  bash/zsh on macOS). Don't make the user pick.
- **Run commands for the user.** Create the venv, install dependencies, write the config,
  and run each phase yourself.
- **Never print, echo, log, or repeat the Canvas token.** Write it straight into `.env`.
  Do not paste it back into the chat for "confirmation."
- **Pause at every human-decision point** and wait for the user before continuing.
- Each phase is **safe to re-run** — it skips files already downloaded. If something
  fails, retry the same step before troubleshooting.

## Handling the Canvas token securely

The user is likely **not** familiar with how to handle secrets. It's your job to keep
their Canvas token safe. Follow all of these:

- **The token belongs in exactly one place: the `.env` file.** Nowhere else.
- **Before writing it, confirm `.env` is gitignored.** This repo's `.gitignore` already
  lists `.env` (and `course_inventory.csv`, `downloads/`, `logs/`). Verify it's still
  there so the token can never be committed or pushed.
- **Write the token to `.env` using a direct file write/edit — not a shell command.**
  Do not use `echo`, `Set-Content`, `cat`, or similar to insert it, because the token
  would then appear in the terminal scrollback, shell history, and any command logs.
  Edit the file's contents directly so `CANVAS_TOKEN=<their token>` and leave
  `CANVAS_BASE_URL` unchanged.
- **Never print, echo, repeat, summarize, or quote the token back** — not in chat, not in
  a "let me confirm I got it right," not in a commit message, not in a status update.
- **Never put the token in any file other than `.env`**, and never commit `.env`.
- If `verify` fails, don't display the token to debug it — just re-ask the user to paste
  it again and overwrite `.env`.
- Reassure the user: the token only grants access to **their own** courses, it lives only
  on their computer, and they can revoke it anytime at
  Canvas → Settings → Approved Integrations → **Delete**.

> **Most private option (offer it):** if the user would rather their token never pass
> through the chat at all, tell them they can paste it directly into the `.env` file
> themselves (open `.env`, put the token after `CANVAS_TOKEN=`, save) and just say "done."
> Then continue from the verify step. This keeps the token entirely off the AI service.

## Setup sequence

Run these in order, narrating each step.

1. **Check Python.** Run `python --version` (try `python3` on macOS if needed).
   - If it's 3.10 or higher, continue.
   - If it's missing or older, tell the user to install Python 3.10+ from
     https://www.python.org/downloads/ (on Windows they must check **"Add Python to
     PATH"**), then continue once they confirm.

2. **Create the workspace:** `python -m venv .venv`

3. **Activate it:**
   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
     - If activation is blocked by execution policy, run
       `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once, then
       retry.
   - macOS: `source .venv/bin/activate`

4. **Install dependencies:** `pip install -r requirements.txt`

5. **Create the config file** if it doesn't already exist, by copying `.env.example` to
   `.env`.

6. **Get the Canvas token.** Walk the user through generating it (don't try to do this
   yourself — it's in their browser):
   1. Go to https://canvas.stanford.edu and sign in.
   2. Profile picture (top-left) → **Settings**.
   3. Scroll to **Approved Integrations** → **+ New Access Token**.
   4. Purpose: anything (e.g. `GSB Archive`). Leave **Expires** blank → **Generate Token**.
   5. Copy the token — Canvas shows it only once.

   Then have the token stored securely — follow
   **[Handling the Canvas token securely](#handling-the-canvas-token-securely)** below.

7. **Verify:** `python -m canvas_export verify`
   - Success shows a small table with the user's name and Stanford email. Tell them it
     worked. If it errors, the token is likely wrong or has stray spaces — re-do step 6.

## Download sequence

8. **Discover courses:** `python -m canvas_export discover`. This lists their courses and,
   by default, files each under its Canvas term (e.g. `Spring 2024`).

9. **Offer to organize (optional) — do this in chat, not via the interactive command.**
   The built-in `categorize` command reads keystrokes from the terminal with `input()`,
   which won't work when you're driving the shell. **Do not run
   `python -m canvas_export categorize`.** Instead, handle categorization conversationally:

   1. Ask the user whether they want to regroup courses by topic or exclude any. If they
      say no, skip to step 10.
   2. Read the course list from **`course_inventory.csv`** in the project root (written by
      `discover`). Show the user each course with its current folder. The relevant columns
      are:
      - **`category`** — the folder name. Blank means "use the Canvas term" (e.g.
        `Spring 2024`). Put a topic name here (e.g. `Finance and Econ`) to group it there.
      - **`include`** — set to `FALSE` to leave a course out of the archive; anything else
        keeps it.
   3. Let the user tell you, in their own words, how to file each course (or in bulk —
      e.g. "put all my finance classes under Finance"). Translate their answers into
      `category` / `include` values.
   4. **Write their choices back into `course_inventory.csv`**, preserving every other
      column and row exactly. Don't change `course_id`, `name`, `term`, etc.
   5. Show them the resulting plan and let them adjust until they're happy.

   This produces the same result as the interactive command, but the user simply types
   their preferences to you in chat.

10. **Preview the layout:** `python -m canvas_export files --dry-run` and show them the
    folder structure. If it looks wrong, go back to step 9 and adjust the CSV.

11. **Download files:** `python -m canvas_export files` (slides, readings, module files).

12. **Download assignments:** `python -m canvas_export assignments` (submissions +
    instructor feedback as PDF, or HTML if PDF conversion isn't available).

## After downloading

The final steps happen in the browser and the user must do them — guide them through:

- **Upload to Google Drive:** install Google Drive for Desktop (mirror files), create a
  folder named exactly **`Stanford Canvas Archive`** in `My Drive`, and copy everything
  inside this repo's `downloads/` folder into it. Wait for sync to finish.
- **Set up Claude search:** create a Claude Project, paste the project instructions from
  the README, connect the `Stanford Canvas Archive` Google Drive folder, and start asking
  questions.

See `README.md` for the exact wording of the Claude project instructions and a full
troubleshooting section.

## Troubleshooting quick reference

- **"CANVAS_TOKEN is not set"** — `.env` is missing or empty; re-do setup step 6.
- **"python is not recognized"** — Python isn't on PATH; reinstall and enable "Add to PATH".
- **Assignments saved as `.html`** — PDF library missing; the HTML is identical, open in a browser.
- **A file failed** — it's skipped; details in `logs/errors.log`; re-running retries it.
