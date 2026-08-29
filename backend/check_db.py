import sqlite3
c = sqlite3.connect('logs.db')
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)
rows = c.execute("SELECT * FROM logs").fetchall()
print("Rows:", rows)