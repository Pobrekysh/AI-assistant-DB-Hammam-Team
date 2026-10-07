import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validator import validate_sql

tests = [
    ("SELECT COUNT(*) FROM applications WHERE program_name='Экономика'", True),
    ("SELECT COUNT(*) FROM teachers", True),
    ("SELECT AVG(g.grade) FROM grades g JOIN student_groups sg ON g.group_id = sg.id", True),
    ("SELECT full_name FROM teachers LIMIT 10", True),
    ("DROP TABLE students", False),
    ("SELECT * FROM users", False),
    ("SELECT * FROM teachers; DROP TABLE teachers", False),
    ("UPDATE teachers SET full_name='x'", False),
    ("INSERT INTO teachers VALUES (1, 'x', 'y')", False),
    ("SELECT * FROM teachers WHERE 1=1 -- comment", False),
    ("SELECT pg_sleep(10)", False),
    ("SELECT * FROM passwords", False),
]

passed = 0
for sql, expected in tests:
    ok, reason = validate_sql(sql)
    status = "OK  " if ok == expected else "FAIL"
    if ok == expected:
        passed += 1
    short = sql[:65] + ("..." if len(sql) > 65 else "")
    print(f"[{status}] {short:70} -> ok={ok} ({reason})")

print(f"\n{passed}/{len(tests)} passed")