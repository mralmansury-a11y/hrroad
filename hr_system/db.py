# -*- coding: utf-8 -*-
"""
طبقة وصول بسيطة لقاعدة بيانات SQLite باستخدام مكتبة sqlite3 القياسية
(لا تعتمد على أي حزمة خارجية مثل SQLAlchemy).
"""
import os
import sqlite3

from flask import g

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "hr_system.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def init_db(connection=None):
    """ينشئ الجداول من schema.sql (يحذف البيانات الحالية إن وجدت)."""
    own_connection = connection is None
    conn = connection or sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    if own_connection:
        conn.close()
