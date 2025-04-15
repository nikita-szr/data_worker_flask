import sqlite3


def init_db():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()