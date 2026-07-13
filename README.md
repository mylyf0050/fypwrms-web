# Final Year Project Work Records Keeping Management System (FYPWRMS) — Web App

A Flask + SQLite web version of the records management system: same data
model as the desktop edition, now running in a browser so it can be
reached from any computer on the department's network.

## Requirements

- Python 3.8+
- Flask (`pip install -r requirements.txt`)

No database server needed — SQLite stores everything in a single file
created automatically on first run.

## Running in Visual Studio Code

1. Unzip this folder and open it in VS Code: **File → Open Folder…** and select `FYPWRMS_Web`.
2. If prompted, install the recommended **Python** extension (VS Code will suggest it automatically — it's listed in `.vscode/extensions.json`).
3. Open a terminal in VS Code (**Terminal → New Terminal**) and create a virtual environment:
   ```
   python -m venv venv
   ```
   Activate it:
   - **Windows:** `venv\Scripts\activate`
   - **macOS / Linux:** `source venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Click the Python interpreter name in the bottom-right status bar and select the `venv` one you just created (VS Code usually detects it automatically and asks).
6. Run the app one of two ways:
   - **Press F5** (uses the included `.vscode/launch.json` config, runs with the debugger attached — breakpoints work), or
   - In the terminal: `python app.py`
7. Open **http://127.0.0.1:5000** in a browser.

The `.vscode/` folder included here already has the debug configuration and extension recommendation set up, so steps 2 and 6 should mostly happen on their own.

## Running from any terminal (without VS Code)

```
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in a browser.

To make it reachable from other computers on the same network, change
the last line of `app.py` to `app.run(host="0.0.0.0", port=5000)` and
share your machine's local IP address with colleagues.

## Default login

```
Username: admin
Password: admin123
```

Change it from a Python shell:
```python
import database as db
db.change_password("admin", "your_new_password")
```

## Project structure

```
FYPWRMS_Web/
├── app.py                 Flask routes (auth, students, supervisors, projects, reports)
├── database.py             SQLite schema and data access functions
├── requirements.txt
├── fypwrms.db               Created automatically on first run
├── templates/
│   ├── base.html            Sidebar layout shared by all logged-in pages
│   ├── login.html
│   ├── dashboard.html
│   ├── students.html
│   ├── supervisors.html
│   ├── projects.html
│   ├── reports.html
│   └── 404.html
└── static/
    └── style.css             All styling
```

## What it does

Functionally identical to the desktop edition:

- **Students / Supervisors** — add, edit, delete; each field validated server-side.
- **Projects** — link a student to a supervisor, track status (Ongoing →
  Submitted → Defended → Graded), proposal/submission/defense dates, grade,
  and remarks. Search box filters by title, student, supervisor, or status.
- **Dashboard** — record counts by status.
- **Reports** — one-click CSV download for each of the three record types.

Deleting a student removes their project record too (a project can't
exist without a student). Deleting a supervisor leaves their assigned
projects in place with the supervisor slot cleared, so a departing
lecturer's projects aren't lost — they just need reassigning.

## Testing performed

Before delivery this was exercised end-to-end with a headless browser
(Playwright): login (success and failure), adding/editing/deleting
records in all three tables, search with and without matches, the
supervisor-delete-keeps-project and student-delete-removes-project
behaviors, CSV export, duplicate-key error handling, unauthenticated
redirect to login, and a mobile viewport check to confirm the wide
projects table scrolls inside its own container rather than breaking
the page layout. No server errors were logged during any of these runs.

## Notes on scope

Single admin role, single SQLite file, no email notifications or PDF
export — the same scope as the desktop edition, just reachable over
HTTP instead of run locally. See the project report's "Recommendations
for Future Work" section for natural next steps (supervisor login role,
a proper multi-user database, calendar-style date pickers, etc.).
