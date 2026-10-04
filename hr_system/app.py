# -*- coding: utf-8 -*-
"""
نظام إدارة الموارد البشرية - الجهاز الوطني للتنمية
تطبيق Flask + SQLite (بدون أي حزم خارجية غير Flask نفسه)

الواجهات المُفعّلة وظيفياً في هذه النسخة:
  1) تسجيل الدخول (/login)   - تحقق فعلي من قاعدة البيانات + جلسات Flask
  2) لوحة التحكم (/dashboard) - بيانات حيّة (KPIs، حضور آخر 7 أيام، طلبات إجازة، عقود تنتهي قريباً)

باقي الوحدات (الموظفون، الحضور، الإجازات، الرواتب، الأداء...) ما زالت
واجهات "قيد التطوير" كما في التصميم الأصلي، ويمكن ربطها بنفس الطريقة
(استعلامات SQL مباشرة عبر db.py) في المرحلة القادمة.
"""
import os
from datetime import date, timedelta, datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import check_password_hash

import db

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db.init_app(app)


# ---------------------------------------------------------------------------
# أدوات مساعدة
# ---------------------------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


ARABIC_WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def get_current_user():
    """يجلب المستخدم الحالي مع بيانات الموظف المرتبط به (إن وجد)."""
    conn = db.get_db()
    row = conn.execute(
        """
        SELECT u.id, u.username, u.role, u.employee_id,
               e.full_name, e.initials, e.position,
               d.name AS department_name
        FROM users u
        LEFT JOIN employees e ON e.id = u.employee_id
        LEFT JOIN departments d ON d.id = e.department_id
        WHERE u.id = ?
        """,
        (session["user_id"],),
    ).fetchone()
    return row


# ---------------------------------------------------------------------------
# 1) واجهة تسجيل الدخول
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = db.get_db()
        user = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        flash("اسم المستخدم أو كلمة المرور غير صحيحة", "error")
        return render_template("login.html", username=username), 401

    return render_template("login.html", username="")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# 2) واجهة لوحة التحكم (Overview) - بيانات حية من قاعدة البيانات
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = db.get_db()
    current_user = get_current_user()
    today = date.today()
    today_str = today.isoformat()

    # ---- KPIs ----
    total_employees = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]

    pending_leaves_count = conn.execute(
        "SELECT COUNT(*) AS c FROM leave_requests WHERE status = 'pending'"
    ).fetchone()["c"]

    present_today = conn.execute(
        "SELECT COUNT(*) AS c FROM attendance WHERE day = ? AND status IN ('present','late')",
        (today_str,),
    ).fetchone()["c"]
    attendance_rate = round((present_today / total_employees) * 100) if total_employees else 0

    upcoming_limit = (today + timedelta(days=30)).isoformat()
    contracts_ending_rows = conn.execute(
        """
        SELECT e.*, d.name AS department_name
        FROM employees e
        JOIN departments d ON d.id = e.department_id
        WHERE e.contract_end_date IS NOT NULL
          AND e.contract_end_date >= ?
          AND e.contract_end_date <= ?
        ORDER BY e.contract_end_date ASC
        """,
        (today_str, upcoming_limit),
    ).fetchall()

    contracts_ending = []
    for row in contracts_ending_rows:
        end_date = parse_date(row["contract_end_date"])
        contracts_ending.append({
            "full_name": row["full_name"],
            "initials": row["initials"],
            "position": row["position"],
            "department_name": row["department_name"],
            "contract_type": row["contract_type"],
            "contract_end_date": end_date,
            "days_left": (end_date - today).days,
        })

    # ---- معدل الحضور لآخر 7 أيام (لرسم الأعمدة) ----
    weekly_chart = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        present = conn.execute(
            "SELECT COUNT(*) AS c FROM attendance WHERE day = ? AND status IN ('present','late')",
            (day_str,),
        ).fetchone()["c"]
        rate = round((present / total_employees) * 100) if total_employees else 0
        weekly_chart.append({"label": ARABIC_WEEKDAYS[day.weekday()], "rate": rate})

    # ---- طلبات إجازة قيد المراجعة (آخر 4) ----
    pending_leaves = conn.execute(
        """
        SELECT lr.id, lr.leave_type, lr.days, e.full_name, e.initials
        FROM leave_requests lr
        JOIN employees e ON e.id = lr.employee_id
        WHERE lr.status = 'pending'
        ORDER BY lr.created_at DESC
        LIMIT 4
        """
    ).fetchall()

    context = {
        "current_user": current_user,
        "total_employees": total_employees,
        "pending_leaves_count": pending_leaves_count,
        "present_today": present_today,
        "attendance_rate": attendance_rate,
        "contracts_ending": contracts_ending,
        "contracts_ending_count": len(contracts_ending),
        "weekly_chart": weekly_chart,
        "pending_leaves": pending_leaves,
        "today": today,
    }
    return render_template("dashboard.html", **context)


# ---------------------------------------------------------------------------
# إجراء سريع: قبول / رفض طلب إجازة من لوحة التحكم (وظيفة حية بسيطة)
# ---------------------------------------------------------------------------
@app.route("/leave-requests/<int:request_id>/<string:decision>", methods=["POST"])
@login_required
def decide_leave_request(request_id, decision):
    if decision not in ("approve", "reject"):
        flash("إجراء غير معروف", "error")
        return redirect(url_for("dashboard"))

    conn = db.get_db()
    new_status = "approved" if decision == "approve" else "rejected"
    conn.execute(
        "UPDATE leave_requests SET status = ? WHERE id = ?",
        (new_status, request_id),
    )
    conn.commit()
    flash("تم تحديث حالة الطلب بنجاح", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# وحدات لاحقة (الموظفون، الحضور، الإجازات، الرواتب، الأداء...) - قيد التطوير
# روابط الشريط الجانبي تعمل وتعرض حالة "قيد التطوير" ريثما يتم ربطها بالبيانات
# ---------------------------------------------------------------------------
MODULE_LABELS = {
    "employees": "الموظفون",
    "attendance": "الحضور والانصراف",
    "leaves": "الإجازات",
    "payroll": "الرواتب",
    "performance": "الأداء",
    "recruitment": "التوظيف",
    "training": "التدريب والتطوير",
}


@app.route("/module/<string:key>")
@login_required
def module_placeholder(key):
    label = MODULE_LABELS.get(key, "هذه الوحدة")
    return render_template(
        "soon.html",
        module_label=label,
        active_panel=key,
        current_user=get_current_user(),
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
