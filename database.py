"""
database.py
All database access for the FYPWRMS web app. Supports SQLite for local
development and PostgreSQL for production deployment.
"""

import sqlite3
import hashlib
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Use PostgreSQL if DATABASE_URL is set (production), otherwise SQLite
DATABASE_URL = os.environ.get("DATABASE_URL")
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fypwrms.db")


def get_connection():
    if DATABASE_URL:
        # PostgreSQL connection for production
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    else:
        # SQLite connection for local development
        conn = sqlite3.connect(DB_NAME)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn


def hash_password(raw_password: str) -> str:
    salt = "fypwrms_salt"
    return hashlib.sha256((salt + raw_password).encode("utf-8")).hexdigest()


def initialize_database():
    conn = get_connection()
    cur = conn.cursor()

    if DATABASE_URL:
        # PostgreSQL syntax
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS supervisors (
                id SERIAL PRIMARY KEY,
                staff_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                department TEXT,
                phone TEXT,
                email TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                index_number TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                program TEXT,
                level TEXT,
                phone TEXT,
                email TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                supervisor_id INTEGER,
                academic_year TEXT,
                status TEXT DEFAULT 'Ongoing',
                proposal_date TEXT,
                submission_date TEXT,
                defense_date TEXT,
                grade TEXT,
                remarks TEXT,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
                FOREIGN KEY (supervisor_id) REFERENCES supervisors (id) ON DELETE SET NULL
            )
        """)
    else:
        # SQLite syntax
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS supervisors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                department TEXT,
                phone TEXT,
                email TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_number TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                program TEXT,
                level TEXT,
                phone TEXT,
                email TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                supervisor_id INTEGER,
                academic_year TEXT,
                status TEXT DEFAULT 'Ongoing',
                proposal_date TEXT,
                submission_date TEXT,
                defense_date TEXT,
                grade TEXT,
                remarks TEXT,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
                FOREIGN KEY (supervisor_id) REFERENCES supervisors (id) ON DELETE SET NULL
            )
        """)

    if DATABASE_URL:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_students (
                project_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (project_id, student_id),
                UNIQUE (project_id, position),
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            INSERT INTO project_students (project_id, student_id, position)
            SELECT p.id, p.student_id, 1 FROM projects p
            WHERE NOT EXISTS (
                SELECT 1 FROM project_students ps
                WHERE ps.project_id = p.id AND ps.student_id = p.student_id
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_students (
                project_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (project_id, student_id),
                UNIQUE (project_id, position),
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            INSERT OR IGNORE INTO project_students (project_id, student_id, position)
            SELECT id, student_id, 1 FROM projects
        """)
        conn.commit()

    if not DATABASE_URL:
        conn.commit()

    # Older installations created this table before accounts had roles.  Adding
    # the column here upgrades those databases in place, so existing records and
    # the administrator account are kept intact.
    if DATABASE_URL:
        cur.execute(
            "ALTER TABLE admins ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'"
        )
        # Ensure admin user has admin role (handle existing users)
        cur.execute("UPDATE admins SET role = 'admin' WHERE username = %s", ("admin",))
    else:
        # Add role column if it doesn't exist (for existing SQLite databases)
        columns = {column[1] for column in cur.execute("PRAGMA table_info(admins)")}
        if "role" not in columns:
            cur.execute("ALTER TABLE admins ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        # Ensure admin user has admin role
        cur.execute("UPDATE admins SET role = ? WHERE username = ?", ("admin", "admin"))
        conn.commit()

    # Optional one-time Render bootstrap: promote an existing account by username.
    bootstrap_admin_username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    if bootstrap_admin_username:
        if DATABASE_URL:
            cur.execute(
                "UPDATE admins SET role = 'admin' WHERE username = %s",
                (bootstrap_admin_username,),
            )
        else:
            cur.execute(
                "UPDATE admins SET role = ? WHERE username = ?",
                ("admin", bootstrap_admin_username),
            )
            conn.commit()
        if cur.rowcount == 0:
            conn.close()
            raise RuntimeError("BOOTSTRAP_ADMIN_USERNAME does not match an existing account")

    conn.close()


# ---------- Authentication ----------

def verify_login(username: str, password: str) -> bool:
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT password_hash FROM admins WHERE username = %s", (username,)
        )
        row = cur.fetchone()
    else:
        row = conn.execute(
            "SELECT password_hash FROM admins WHERE username = ?", (username,)
        ).fetchone()
    conn.close()
    if row is None:
        return False
    return row["password_hash"] == hash_password(password)


def change_password(username: str, new_password: str):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "UPDATE admins SET password_hash = %s WHERE username = %s",
            (hash_password(new_password), username),
        )
    else:
        conn.execute(
            "UPDATE admins SET password_hash = ? WHERE username = ?",
            (hash_password(new_password), username),
        )
        conn.commit()
    conn.close()


def register_user(username: str, password: str) -> bool:
    """Register a new user. Returns True if successful, False if username exists."""
    conn = get_connection()
    try:
        if DATABASE_URL:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO admins (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, hash_password(password), "user"),
            )
        else:
            conn.execute(
                "INSERT INTO admins (username, password_hash, role) VALUES (?, ?, ?)",
                (username, hash_password(password), "user"),
            )
            conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False


def get_user_role(username: str) -> str:
    """Get the role of a user. Returns 'user' if not found."""
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT role FROM admins WHERE username = %s", (username,))
        row = cur.fetchone()
        conn.close()
        return row["role"] if row else "user"
    else:
        row = conn.execute("SELECT role FROM admins WHERE username = ?", (username,)).fetchone()
        conn.close()
        return row["role"] if row else "user"


# ---------- Supervisors ----------

def add_supervisor(staff_id, full_name, department, phone, email):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO supervisors (staff_id, full_name, department, phone, email) "
            "VALUES (%s, %s, %s, %s, %s)",
            (staff_id, full_name, department, phone, email),
        )
    else:
        conn.execute(
            "INSERT INTO supervisors (staff_id, full_name, department, phone, email) "
            "VALUES (?, ?, ?, ?, ?)",
            (staff_id, full_name, department, phone, email),
        )
        conn.commit()
    conn.close()


def update_supervisor(sup_id, staff_id, full_name, department, phone, email):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "UPDATE supervisors SET staff_id=%s, full_name=%s, department=%s, phone=%s, email=%s "
            "WHERE id=%s",
            (staff_id, full_name, department, phone, email, sup_id),
        )
    else:
        conn.execute(
            "UPDATE supervisors SET staff_id=?, full_name=?, department=?, phone=?, email=? "
            "WHERE id=?",
            (staff_id, full_name, department, phone, email, sup_id),
        )
        conn.commit()
    conn.close()


def delete_supervisor(sup_id):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute("DELETE FROM supervisors WHERE id=%s", (sup_id,))
    else:
        conn.execute("DELETE FROM supervisors WHERE id=?", (sup_id,))
        conn.commit()
    conn.close()


def get_supervisor(sup_id):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM supervisors WHERE id=%s", (sup_id,))
        row = cur.fetchone()
    else:
        row = conn.execute("SELECT * FROM supervisors WHERE id=?", (sup_id,)).fetchone()
    conn.close()
    return row


def get_all_supervisors():
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM supervisors ORDER BY full_name")
        rows = cur.fetchall()
    else:
        rows = conn.execute("SELECT * FROM supervisors ORDER BY full_name").fetchall()
    conn.close()
    return rows


def search_supervisors(keyword):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM supervisors WHERE staff_id ILIKE %s OR full_name ILIKE %s OR department ILIKE %s ORDER BY full_name",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        )
        rows = cur.fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM supervisors WHERE staff_id LIKE ? OR full_name LIKE ? OR department LIKE ? ORDER BY full_name",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        ).fetchall()
    conn.close()
    return rows


# ---------- Students ----------

def add_student(index_number, full_name, program, level, phone, email):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO students (index_number, full_name, program, level, phone, email) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (index_number, full_name, program, level, phone, email),
        )
    else:
        conn.execute(
            "INSERT INTO students (index_number, full_name, program, level, phone, email) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (index_number, full_name, program, level, phone, email),
        )
        conn.commit()
    conn.close()


def update_student(student_id, index_number, full_name, program, level, phone, email):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "UPDATE students SET index_number=%s, full_name=%s, program=%s, level=%s, "
            "phone=%s, email=%s WHERE id=%s",
            (index_number, full_name, program, level, phone, email, student_id),
        )
    else:
        conn.execute(
            "UPDATE students SET index_number=?, full_name=?, program=?, level=?, "
            "phone=?, email=? WHERE id=?",
            (index_number, full_name, program, level, phone, email, student_id),
        )
        conn.commit()
    conn.close()


def delete_student(student_id):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            """SELECT id FROM projects
               WHERE student_id = %s
                 AND EXISTS (
                     SELECT 1 FROM project_students ps
                     WHERE ps.project_id = projects.id AND ps.student_id <> %s
                 )""",
            (student_id, student_id),
        )
        project_ids = [row[0] for row in cur.fetchall()]
        for project_id in project_ids:
            cur.execute(
                """SELECT student_id FROM project_students
                   WHERE project_id = %s AND student_id <> %s
                   ORDER BY position LIMIT 1""",
                (project_id, student_id),
            )
            replacement = cur.fetchone()
            if replacement:
                cur.execute("UPDATE projects SET student_id = %s WHERE id = %s",
                            (replacement[0], project_id))
        cur.execute("DELETE FROM students WHERE id=%s", (student_id,))
    else:
        project_ids = conn.execute(
            """SELECT id FROM projects
               WHERE student_id = ?
                 AND EXISTS (
                     SELECT 1 FROM project_students ps
                     WHERE ps.project_id = projects.id AND ps.student_id <> ?
                 )""",
            (student_id, student_id),
        ).fetchall()
        for row in project_ids:
            replacement = conn.execute(
                """SELECT student_id FROM project_students
                   WHERE project_id = ? AND student_id <> ?
                   ORDER BY position LIMIT 1""",
                (row["id"], student_id),
            ).fetchone()
            if replacement:
                conn.execute("UPDATE projects SET student_id = ? WHERE id = ?",
                             (replacement["student_id"], row["id"]))
        conn.execute("DELETE FROM students WHERE id=?", (student_id,))
        conn.commit()
    conn.close()


def get_student(student_id):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM students WHERE id=%s", (student_id,))
        row = cur.fetchone()
    else:
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    conn.close()
    return row


def get_all_students():
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM students ORDER BY full_name")
        rows = cur.fetchall()
    else:
        rows = conn.execute("SELECT * FROM students ORDER BY full_name").fetchall()
    conn.close()
    return rows


def search_students(keyword):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM students WHERE index_number ILIKE %s OR full_name ILIKE %s OR program ILIKE %s OR level ILIKE %s ORDER BY full_name",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        )
        rows = cur.fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM students WHERE index_number LIKE ? OR full_name LIKE ? OR program LIKE ? OR level LIKE ? ORDER BY full_name",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        ).fetchall()
    conn.close()
    return rows


# ---------- Projects ----------

def _replace_project_students(conn, project_id, student_ids):
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute("DELETE FROM project_students WHERE project_id = %s", (project_id,))
        cur.executemany(
            "INSERT INTO project_students (project_id, student_id, position) VALUES (%s, %s, %s)",
            [(project_id, sid, pos) for pos, sid in enumerate(student_ids, 1)],
        )
    else:
        conn.execute("DELETE FROM project_students WHERE project_id = ?", (project_id,))
        conn.executemany(
            "INSERT INTO project_students (project_id, student_id, position) VALUES (?, ?, ?)",
            [(project_id, sid, pos) for pos, sid in enumerate(student_ids, 1)],
        )


def add_project(title, student_ids, supervisor_id, academic_year, status,
                 proposal_date, submission_date, defense_date, grade, remarks):
    student_ids = list(dict.fromkeys(student_ids or []))
    if not student_ids:
        raise ValueError("Select at least one student for the project.")
    conn = get_connection()
    primary_student_id = student_ids[0]
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO projects
               (title, student_id, supervisor_id, academic_year, status,
                proposal_date, submission_date, defense_date, grade, remarks)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (title, primary_student_id, supervisor_id, academic_year, status,
             proposal_date, submission_date, defense_date, grade, remarks),
        )
        project_id = cur.fetchone()[0]
    else:
        cur = conn.execute(
            """INSERT INTO projects
               (title, student_id, supervisor_id, academic_year, status,
                proposal_date, submission_date, defense_date, grade, remarks)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, primary_student_id, supervisor_id, academic_year, status,
             proposal_date, submission_date, defense_date, grade, remarks),
        )
        project_id = cur.lastrowid
    _replace_project_students(conn, project_id, student_ids)
    if not DATABASE_URL:
        conn.commit()
    conn.close()


def update_project(project_id, title, student_ids, supervisor_id, academic_year,
                    status, proposal_date, submission_date, defense_date, grade, remarks):
    student_ids = list(dict.fromkeys(student_ids or []))
    if not student_ids:
        raise ValueError("Select at least one student for the project.")
    conn = get_connection()
    primary_student_id = student_ids[0]
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            """UPDATE projects SET title=%s, student_id=%s, supervisor_id=%s, academic_year=%s,
               status=%s, proposal_date=%s, submission_date=%s, defense_date=%s, grade=%s, remarks=%s
               WHERE id=%s""",
            (title, primary_student_id, supervisor_id, academic_year, status, proposal_date,
             submission_date, defense_date, grade, remarks, project_id),
        )
    else:
        conn.execute(
            """UPDATE projects SET title=?, student_id=?, supervisor_id=?, academic_year=?,
               status=?, proposal_date=?, submission_date=?, defense_date=?, grade=?, remarks=?
               WHERE id=?""",
            (title, primary_student_id, supervisor_id, academic_year, status, proposal_date,
             submission_date, defense_date, grade, remarks, project_id),
        )
    _replace_project_students(conn, project_id, student_ids)
    if not DATABASE_URL:
        conn.commit()
    conn.close()


def delete_project(project_id):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute("DELETE FROM projects WHERE id=%s", (project_id,))
    else:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        conn.commit()
    conn.close()


def _attach_project_students(conn, rows):
    if not rows:
        return []
    project_ids = [row["id"] for row in rows]
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT ps.project_id, s.id, s.full_name, s.index_number
            FROM project_students ps JOIN students s ON s.id = ps.student_id
            WHERE ps.project_id = ANY(%s)
            ORDER BY ps.project_id, ps.position
        """, (project_ids,))
        member_rows = cur.fetchall()
    else:
        marks = ",".join("?" for _ in project_ids)
        member_rows = conn.execute(
            f"""SELECT ps.project_id, s.id, s.full_name, s.index_number
                FROM project_students ps JOIN students s ON s.id = ps.student_id
                WHERE ps.project_id IN ({marks}) ORDER BY ps.project_id, ps.position""",
            project_ids,
        ).fetchall()
    grouped = {}
    for member in member_rows:
        grouped.setdefault(member["project_id"], []).append({
            "id": member["id"], "full_name": member["full_name"],
            "index_number": member["index_number"],
        })
    result = []
    for row in rows:
        project = dict(row)
        members = grouped.get(project["id"], [])
        project["students"] = members
        project["student_ids"] = [m["id"] for m in members]
        project["student_names"] = ", ".join(m["full_name"] for m in members)
        project["student_index_numbers"] = ", ".join(m["index_number"] for m in members)
        project["student_count"] = len(members)
        result.append(project)
    return result


def get_project(project_id):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        row = cur.fetchone()
    else:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    rows = _attach_project_students(conn, [row]) if row else []
    conn.close()
    return rows[0] if rows else None


def get_all_projects():
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.id, p.title, sup.full_name AS supervisor_name,
                   p.academic_year, p.status, p.proposal_date, p.submission_date,
                   p.defense_date, p.grade, p.remarks, p.student_id, p.supervisor_id
                   FROM projects p LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
                   ORDER BY p.academic_year DESC, p.title""")
        rows = cur.fetchall()
    else:
        rows = conn.execute("""SELECT p.id, p.title, sup.full_name AS supervisor_name,
                   p.academic_year, p.status, p.proposal_date, p.submission_date,
                   p.defense_date, p.grade, p.remarks, p.student_id, p.supervisor_id
                   FROM projects p LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
                   ORDER BY p.academic_year DESC, p.title""").fetchall()
    rows = _attach_project_students(conn, rows)
    conn.close()
    return rows


def search_projects(keyword):
    conn = get_connection()
    like = f"%{keyword}%"
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT p.id, p.title, sup.full_name AS supervisor_name,
                   p.academic_year, p.status, p.proposal_date, p.submission_date,
                   p.defense_date, p.grade, p.remarks, p.student_id, p.supervisor_id
                   FROM projects p LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
                   WHERE p.title ILIKE %s OR p.status ILIKE %s OR sup.full_name ILIKE %s
                     OR EXISTS (SELECT 1 FROM project_students ps JOIN students s ON s.id=ps.student_id
                                WHERE ps.project_id=p.id AND (s.full_name ILIKE %s OR s.index_number ILIKE %s))
                   ORDER BY p.academic_year DESC, p.title""", (like, like, like, like, like))
        rows = cur.fetchall()
    else:
        rows = conn.execute("""SELECT p.id, p.title, sup.full_name AS supervisor_name,
                   p.academic_year, p.status, p.proposal_date, p.submission_date,
                   p.defense_date, p.grade, p.remarks, p.student_id, p.supervisor_id
                   FROM projects p LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
                   WHERE p.title LIKE ? OR p.status LIKE ? OR sup.full_name LIKE ?
                     OR EXISTS (SELECT 1 FROM project_students ps JOIN students s ON s.id=ps.student_id
                                WHERE ps.project_id=p.id AND (s.full_name LIKE ? OR s.index_number LIKE ?))
                   ORDER BY p.academic_year DESC, p.title""", (like, like, like, like, like)).fetchall()
    rows = _attach_project_students(conn, rows)
    conn.close()
    return rows


def get_dashboard_counts():
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) AS c FROM students")
        total_students = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM supervisors")
        total_supervisors = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM projects")
        total_projects = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM projects WHERE status='Ongoing'")
        ongoing = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM projects WHERE status='Submitted'")
        submitted = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM projects WHERE status='Defended'")
        defended = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM projects WHERE status='Graded'")
        graded = cur.fetchone()["c"]
    else:
        total_students = conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
        total_supervisors = conn.execute("SELECT COUNT(*) c FROM supervisors").fetchone()["c"]
        total_projects = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
        ongoing = conn.execute("SELECT COUNT(*) c FROM projects WHERE status='Ongoing'").fetchone()["c"]
        submitted = conn.execute("SELECT COUNT(*) c FROM projects WHERE status='Submitted'").fetchone()["c"]
        defended = conn.execute("SELECT COUNT(*) c FROM projects WHERE status='Defended'").fetchone()["c"]
        graded = conn.execute("SELECT COUNT(*) c FROM projects WHERE status='Graded'").fetchone()["c"]
    conn.close()
    return {
        "students": total_students,
        "supervisors": total_supervisors,
        "projects": total_projects,
        "ongoing": ongoing,
        "submitted": submitted,
        "defended": defended,
        "graded": graded,
    }
