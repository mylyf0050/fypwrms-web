"""
app.py
Flask entry point for the FYPWRMS web app.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

import csv
import io
import os
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response
)

import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("FYPWRMS_SECRET_KEY", "dev-secret-key-change-in-production")

STATUS_OPTIONS = ["Ongoing", "Submitted", "Defended", "Graded"]

# Initialize database on startup
db.initialize_database()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("username"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("username"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "current_user": session.get("username"),
        "current_role": session.get("role"),
        "status_options": STATUS_OPTIONS
    }


# ---------------- Auth ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("username"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            flash("Enter both username and password.", "error")
        elif db.verify_login(username, password):
            session["username"] = username
            session["role"] = db.get_user_role(username)
            return redirect(url_for("dashboard"))
        else:
            flash("Incorrect username or password.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("username"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        
        if not username or not password:
            flash("Username and password are required.", "error")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif db.register_user(username, password):
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Username already exists. Please choose another.", "error")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------- Dashboard ----------------

@app.route("/")
@login_required
def dashboard():
    counts = db.get_dashboard_counts()
    recent_projects = db.get_all_projects()[:5]
    return render_template("dashboard.html", counts=counts, recent_projects=recent_projects)


# ---------------- Students ----------------

@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    editing_id = request.args.get("edit", type=int)
    editing_student = db.get_student(editing_id) if editing_id else None

    if request.method == "POST":
        form_id = request.form.get("id", type=int)
        values = {
            "index_number": request.form.get("index_number", "").strip(),
            "full_name": request.form.get("full_name", "").strip(),
            "program": request.form.get("program", "").strip(),
            "level": request.form.get("level", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
        }
        if not values["index_number"] or not values["full_name"]:
            flash("Index number and full name are required.", "error")
            return redirect(url_for("students", edit=form_id) if form_id else url_for("students"))

        try:
            if form_id:
                db.update_student(form_id, **values)
                flash("Student record updated.", "success")
            else:
                db.add_student(**values)
                flash("Student added.", "success")
        except Exception as exc:
            flash(f"Could not save student: {exc}", "error")
        return redirect(url_for("students"))

    return render_template("students.html", students=db.get_all_students(), editing=editing_student)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@admin_required
def delete_student(student_id):
    db.delete_student(student_id)
    flash("Student and any linked project records were removed.", "success")
    return redirect(url_for("students"))


# ---------------- Supervisors ----------------

@app.route("/supervisors", methods=["GET", "POST"])
@login_required
def supervisors():
    editing_id = request.args.get("edit", type=int)
    editing_supervisor = db.get_supervisor(editing_id) if editing_id else None

    if request.method == "POST":
        if session.get("role") != "admin":
            flash("Admin access required to add or edit supervisors.", "error")
            return redirect(url_for("supervisors"))
        
        form_id = request.form.get("id", type=int)
        values = {
            "staff_id": request.form.get("staff_id", "").strip(),
            "full_name": request.form.get("full_name", "").strip(),
            "department": request.form.get("department", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
        }
        if not values["staff_id"] or not values["full_name"]:
            flash("Staff ID and full name are required.", "error")
            return redirect(url_for("supervisors", edit=form_id) if form_id else url_for("supervisors"))

        try:
            if form_id:
                db.update_supervisor(form_id, **values)
                flash("Supervisor record updated.", "success")
            else:
                db.add_supervisor(**values)
                flash("Supervisor added.", "success")
        except Exception as exc:
            flash(f"Could not save supervisor: {exc}", "error")
        return redirect(url_for("supervisors"))

    return render_template("supervisors.html", supervisors=db.get_all_supervisors(), editing=editing_supervisor)


@app.route("/supervisors/<int:sup_id>/delete", methods=["POST"])
@admin_required
def delete_supervisor(sup_id):
    db.delete_supervisor(sup_id)
    flash("Supervisor removed. Any assigned projects now show no supervisor.", "success")
    return redirect(url_for("supervisors"))


# ---------------- Projects ----------------

@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    editing_id = request.args.get("edit", type=int)
    editing_project = db.get_project(editing_id) if editing_id else None
    keyword = request.args.get("q", "").strip()

    if request.method == "POST":
        if session.get("role") != "admin":
            flash("Admin access required to add or edit projects.", "error")
            return redirect(url_for("projects"))
        
        form_id = request.form.get("id", type=int)
        student_id = request.form.get("student_id", type=int)
        supervisor_id = request.form.get("supervisor_id", type=int) or None
        values = {
            "title": request.form.get("title", "").strip(),
            "student_id": student_id,
            "supervisor_id": supervisor_id,
            "academic_year": request.form.get("academic_year", "").strip(),
            "status": request.form.get("status", STATUS_OPTIONS[0]),
            "proposal_date": request.form.get("proposal_date", "").strip() or None,
            "submission_date": request.form.get("submission_date", "").strip() or None,
            "defense_date": request.form.get("defense_date", "").strip() or None,
            "grade": request.form.get("grade", "").strip() or None,
            "remarks": request.form.get("remarks", "").strip() or None,
        }
        if not values["title"] or not values["student_id"]:
            flash("Project title and student are required.", "error")
            return redirect(url_for("projects", edit=form_id) if form_id else url_for("projects"))

        try:
            if form_id:
                db.update_project(form_id, **values)
                flash("Project record updated.", "success")
            else:
                db.add_project(**values)
                flash("Project added.", "success")
        except Exception as exc:
            flash(f"Could not save project: {exc}", "error")
        return redirect(url_for("projects"))

    project_rows = db.search_projects(keyword) if keyword else db.get_all_projects()
    return render_template(
        "projects.html",
        projects=project_rows,
        students=db.get_all_students(),
        supervisors=db.get_all_supervisors(),
        editing=editing_project,
        keyword=keyword,
    )


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
@admin_required
def delete_project(project_id):
    db.delete_project(project_id)
    flash("Project record removed.", "success")
    return redirect(url_for("projects"))


# ---------------- Reports (CSV export) ----------------

@app.route("/reports")
@login_required
def reports():
    return render_template("reports.html")


def _csv_response(filename, header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/reports/students.csv")
@login_required
def export_students():
    header = ["Index Number", "Full Name", "Program", "Level", "Phone", "Email"]
    rows = [[s["index_number"], s["full_name"], s["program"], s["level"], s["phone"], s["email"]]
            for s in db.get_all_students()]
    return _csv_response("students.csv", header, rows)


@app.route("/reports/supervisors.csv")
@login_required
def export_supervisors():
    header = ["Staff ID", "Full Name", "Department", "Phone", "Email"]
    rows = [[s["staff_id"], s["full_name"], s["department"], s["phone"], s["email"]]
            for s in db.get_all_supervisors()]
    return _csv_response("supervisors.csv", header, rows)


@app.route("/reports/projects.csv")
@login_required
def export_projects():
    header = ["Title", "Student", "Index Number", "Supervisor", "Academic Year",
              "Status", "Proposal Date", "Submission Date", "Defense Date", "Grade", "Remarks"]
    rows = [[p["title"], p["student_name"], p["index_number"], p["supervisor_name"],
             p["academic_year"], p["status"], p["proposal_date"], p["submission_date"],
             p["defense_date"], p["grade"], p["remarks"]] for p in db.get_all_projects()]
    return _csv_response("projects.csv", header, rows)


# ---------------- Errors ----------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
