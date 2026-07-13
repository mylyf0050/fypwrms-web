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
                password_hash TEXT NOT NULL
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
                password_hash TEXT NOT NULL
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

    if not DATABASE_URL:
        conn.commit()

    cur.execute("SELECT COUNT(*) AS c FROM admins")
    result = cur.fetchone()
    count = result["c"] if DATABASE_URL else result["c"]
    
    if count == 0:
        if DATABASE_URL:
            cur.execute(
                "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                ("admin", hash_password("admin123")),
            )
        else:
            cur.execute(
                "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                ("admin", hash_password("admin123")),
            )
        if not DATABASE_URL:
            conn.commit()

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
        cur.execute("DELETE FROM students WHERE id=%s", (student_id,))
    else:
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


# ---------- Projects ----------

def add_project(title, student_id, supervisor_id, academic_year, status,
                 proposal_date, submission_date, defense_date, grade, remarks):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO projects
               (title, student_id, supervisor_id, academic_year, status,
                proposal_date, submission_date, defense_date, grade, remarks)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (title, student_id, supervisor_id, academic_year, status,
             proposal_date, submission_date, defense_date, grade, remarks),
        )
    else:
        conn.execute(
            """INSERT INTO projects
               (title, student_id, supervisor_id, academic_year, status,
                proposal_date, submission_date, defense_date, grade, remarks)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, student_id, supervisor_id, academic_year, status,
             proposal_date, submission_date, defense_date, grade, remarks),
        )
        conn.commit()
    conn.close()


def update_project(project_id, title, student_id, supervisor_id, academic_year,
                    status, proposal_date, submission_date, defense_date, grade, remarks):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            """UPDATE projects SET title=%s, student_id=%s, supervisor_id=%s, academic_year=%s,
               status=%s, proposal_date=%s, submission_date=%s, defense_date=%s, grade=%s, remarks=%s
               WHERE id=%s""",
            (title, student_id, supervisor_id, academic_year, status, proposal_date,
             submission_date, defense_date, grade, remarks, project_id),
        )
    else:
        conn.execute(
            """UPDATE projects SET title=?, student_id=?, supervisor_id=?, academic_year=?,
               status=?, proposal_date=?, submission_date=?, defense_date=?, grade=?, remarks=?
               WHERE id=?""",
            (title, student_id, supervisor_id, academic_year, status, proposal_date,
             submission_date, defense_date, grade, remarks, project_id),
        )
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


def get_project(project_id):
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
        row = cur.fetchone()
    else:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return row


def get_all_projects():
    conn = get_connection()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT p.id, p.title, s.full_name AS student_name, s.index_number,
                   sup.full_name AS supervisor_name, p.academic_year, p.status,
                   p.proposal_date, p.submission_date, p.defense_date, p.grade, p.remarks,
                   p.student_id, p.supervisor_id
            FROM projects p
            JOIN students s ON p.student_id = s.id
            LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
            ORDER BY p.academic_year DESC, s.full_name
        """)
        rows = cur.fetchall()
    else:
        rows = conn.execute("""
            SELECT p.id, p.title, s.full_name AS student_name, s.index_number,
                   sup.full_name AS supervisor_name, p.academic_year, p.status,
                   p.proposal_date, p.submission_date, p.defense_date, p.grade, p.remarks,
                   p.student_id, p.supervisor_id
            FROM projects p
            JOIN students s ON p.student_id = s.id
            LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
            ORDER BY p.academic_year DESC, s.full_name
        """).fetchall()
    conn.close()
    return rows


def search_projects(keyword):
    conn = get_connection()
    like = f"%{keyword}%"
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT p.id, p.title, s.full_name AS student_name, s.index_number,
                   sup.full_name AS supervisor_name, p.academic_year, p.status,
                   p.proposal_date, p.submission_date, p.defense_date, p.grade, p.remarks,
                   p.student_id, p.supervisor_id
            FROM projects p
            JOIN students s ON p.student_id = s.id
            LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
            WHERE p.title LIKE %s OR s.full_name LIKE %s OR s.index_number LIKE %s
               OR sup.full_name LIKE %s OR p.status LIKE %s
            ORDER BY s.full_name
        """, (like, like, like, like, like))
        rows = cur.fetchall()
    else:
        rows = conn.execute("""
            SELECT p.id, p.title, s.full_name AS student_name, s.index_number,
                   sup.full_name AS supervisor_name, p.academic_year, p.status,
                   p.proposal_date, p.submission_date, p.defense_date, p.grade, p.remarks,
                   p.student_id, p.supervisor_id
            FROM projects p
            JOIN students s ON p.student_id = s.id
            LEFT JOIN supervisors sup ON p.supervisor_id = sup.id
            WHERE p.title LIKE ? OR s.full_name LIKE ? OR s.index_number LIKE ?
               OR sup.full_name LIKE ? OR p.status LIKE ?
            ORDER BY s.full_name
        """, (like, like, like, like, like)).fetchall()
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
