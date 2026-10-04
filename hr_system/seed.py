# -*- coding: utf-8 -*-
"""
سكربت تعبئة البيانات الأولية لقاعدة البيانات.
التشغيل:  python seed.py
"""
import os
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import db as dbmod

DB_PATH = dbmod.DB_PATH


def run():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    dbmod.init_db(connection=conn)

    today = date.today()

    # ---------------- الأقسام ----------------
    dept_names = [
        "الموارد البشرية", "تقنية المعلومات", "المالية",
        "الخدمات الإدارية", "التسويق", "الشؤون القانونية",
    ]
    dept_ids = {}
    for name in dept_names:
        cur = conn.execute("INSERT INTO departments (name) VALUES (?)", (name,))
        dept_ids[name] = cur.lastrowid

    # ---------------- الموظفون ----------------
    employees_data = [
        dict(code="EMP-1042", name="هدى الفقيه", initials="هف",
             dept="الموارد البشرية", position="مسؤول ملفات",
             hire=date(2022, 3, 11), contract="دائم", contract_end=None,
             status="نشط"),
        dict(code="EMP-1187", name="أحمد الككلي", initials="أك",
             dept="تقنية المعلومات", position="مبرمج أنظمة",
             hire=date(2023, 9, 2), contract="مؤقت",
             contract_end=today + timedelta(days=24), status="نشط"),
        dict(code="EMP-1233", name="لمياء مسعود", initials="لم",
             dept="المالية", position="محاسبة أولى",
             hire=date(2025, 5, 20), contract="تجربة",
             contract_end=today + timedelta(days=11), status="إجازة"),
        dict(code="EMP-0987", name="طارق الزنتاني", initials="طز",
             dept="الخدمات الإدارية", position="مسؤول مشتريات",
             hire=date(2021, 1, 15), contract="دائم",
             contract_end=date(2027, 1, 15), status="نشط"),
        dict(code="EMP-1301", name="محمد الطرابلسي", initials="من",
             dept="التسويق", position="منسق إعلام",
             hire=date(2024, 11, 7), contract="دائم", contract_end=None,
             status="نشط"),
        dict(code="EMP-1298", name="سعاد العبيدي", initials="سع",
             dept="التسويق", position="أخصائية تسويق رقمي",
             hire=date(2024, 6, 1), contract="دائم", contract_end=None,
             status="نشط"),
        dict(code="EMP-1310", name="يوسف بشير", initials="يب",
             dept="تقنية المعلومات", position="مهندس شبكات",
             hire=date(2023, 4, 18), contract="دائم", contract_end=None,
             status="نشط"),
        dict(code="EMP-1150", name="رانيا الغزالي", initials="رغ",
             dept="الشؤون القانونية", position="مستشارة قانونية",
             hire=date(2023, 2, 28), contract="دائم", contract_end=None,
             status="إجازة"),
    ]

    emp_ids = {}
    for e in employees_data:
        cur = conn.execute(
            """
            INSERT INTO employees
                (employee_code, full_name, initials, department_id, position,
                 hire_date, contract_type, contract_end_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["code"], e["name"], e["initials"], dept_ids[e["dept"]], e["position"],
                e["hire"].isoformat(), e["contract"],
                e["contract_end"].isoformat() if e["contract_end"] else None,
                e["status"],
            ),
        )
        emp_ids[e["name"]] = cur.lastrowid

    # ---------------- مستخدمو الدخول ----------------
    conn.execute(
        "INSERT INTO users (username, password_hash, role, employee_id) VALUES (?, ?, ?, ?)",
        ("hoda.hr", generate_password_hash("Hr@12345"), "hr", emp_ids["هدى الفقيه"]),
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, role, employee_id) VALUES (?, ?, ?, ?)",
        ("admin", generate_password_hash("Admin@12345"), "admin", None),
    )

    # ---------------- طلبات الإجازات ----------------
    leaves_data = [
        dict(emp="محمد الطرابلسي", type="سنوية",
             start=date(2026, 8, 12), end=date(2026, 8, 14), days=3, status="pending"),
        dict(emp="سعاد العبيدي", type="مرضية",
             start=date(2026, 8, 10), end=date(2026, 8, 10), days=1, status="pending"),
        dict(emp="يوسف بشير", type="طارئة",
             start=date(2026, 8, 5), end=date(2026, 8, 6), days=2, status="approved"),
        dict(emp="رانيا الغزالي", type="بدون راتب",
             start=date(2026, 8, 20), end=date(2026, 8, 24), days=5, status="pending"),
    ]
    for i, lv in enumerate(leaves_data):
        created_at = today - timedelta(days=len(leaves_data) - i)
        conn.execute(
            """
            INSERT INTO leave_requests
                (employee_id, leave_type, start_date, end_date, days, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                emp_ids[lv["emp"]], lv["type"], lv["start"].isoformat(),
                lv["end"].isoformat(), lv["days"], lv["status"], created_at.isoformat(),
            ),
        )

    # ---------------- سجلات الحضور (آخر 7 أيام لكل موظف) ----------------
    daily_rates = [0.78, 0.92, 0.88, 0.95, 0.83, 0.70, 0.0]  # آخر عنصر = الجمعة (عطلة)
    emp_names = list(emp_ids.keys())
    emp_status = {e["name"]: e["status"] for e in employees_data}

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        rate = daily_rates[6 - i]
        for idx, name in enumerate(emp_names):
            emp_id = emp_ids[name]
            if rate == 0:
                continue  # يوم عطلة، لا حضور

            if emp_status[name] == "إجازة" and day == today:
                conn.execute(
                    "INSERT INTO attendance (employee_id, day, check_in, check_out, method, status) "
                    "VALUES (?, ?, NULL, NULL, NULL, 'leave')",
                    (emp_id, day_str),
                )
                continue

            present = (idx / len(emp_names)) < rate
            if present:
                late = idx % 5 == 1
                conn.execute(
                    """
                    INSERT INTO attendance (employee_id, day, check_in, check_out, method, status)
                    VALUES (?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        emp_id, day_str,
                        "08:41 ص" if late else "08:02 ص",
                        "QR المكتب" if idx % 2 == 0 else "GPS ميداني",
                        "late" if late else "present",
                    ),
                )
            else:
                conn.execute(
                    "INSERT INTO attendance (employee_id, day, check_in, check_out, method, status) "
                    "VALUES (?, ?, NULL, NULL, NULL, 'absent')",
                    (emp_id, day_str),
                )

    conn.commit()
    conn.close()

    print("تمت تعبئة قاعدة البيانات بالبيانات الأولية بنجاح.")
    print("بيانات الدخول التجريبية:")
    print("  المستخدم: hoda.hr   | كلمة المرور: Hr@12345")
    print("  المستخدم: admin     | كلمة المرور: Admin@12345")


if __name__ == "__main__":
    run()
