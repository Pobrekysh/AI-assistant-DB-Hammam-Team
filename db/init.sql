-- ============================================================
-- Университетская БД — расширенная схема
-- ============================================================

ALTER DATABASE university_db SET statement_timeout = '5s';

DROP TABLE IF EXISTS grades CASCADE;
DROP TABLE IF EXISTS teacher_subjects CASCADE;
DROP TABLE IF EXISTS subjects CASCADE;
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS student_groups CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS faculties CASCADE;

-- Факультеты
CREATE TABLE faculties (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- Кафедры
CREATE TABLE departments (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    faculty_id INT REFERENCES faculties(id)
);

-- Преподаватели
CREATE TABLE teachers (
    id            SERIAL PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL,
    department_id INT REFERENCES departments(id),
    password      VARCHAR(255),
    passport_data VARCHAR(100)
);

-- Предметы
CREATE TABLE subjects (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    department_id INT REFERENCES departments(id)
);

-- Связь преподаватель ↔ предмет
CREATE TABLE teacher_subjects (
    teacher_id INT REFERENCES teachers(id),
    subject_id INT REFERENCES subjects(id),
    PRIMARY KEY (teacher_id, subject_id)
);

-- Учебные группы
CREATE TABLE student_groups (
    id         SERIAL PRIMARY KEY,
    group_name VARCHAR(50) NOT NULL,
    faculty_id INT REFERENCES faculties(id)
);

-- Заявления
CREATE TABLE applications (
    id               SERIAL PRIMARY KEY,
    program_name     VARCHAR(100) NOT NULL,
    application_year INT NOT NULL,
    status           VARCHAR(50)
);

-- Оценки
CREATE TABLE grades (
    id            SERIAL PRIMARY KEY,
    group_id      INT REFERENCES student_groups(id),
    subject       VARCHAR(100) NOT NULL,
    grade         INT CHECK (grade BETWEEN 2 AND 5),
    semester      INT NOT NULL,
    password      VARCHAR(255),
    passport_data VARCHAR(100)
);

-- ============================================================
-- Данные
-- ============================================================

INSERT INTO faculties (name) VALUES
    ('Факультет информационных технологий'),
    ('Факультет экономики и управления'),
    ('Факультет математики и физики'),
    ('Гуманитарный факультет');

INSERT INTO departments (name, faculty_id) VALUES
    ('Кафедра программирования',      1),
    ('Кафедра информационных систем', 1),
    ('Кафедра экономики',             2),
    ('Кафедра менеджмента',           2),
    ('Кафедра высшей математики',     3),
    ('Кафедра общей физики',          3),
    ('Кафедра истории',               4),
    ('Кафедра иностранных языков',    4);

INSERT INTO subjects (name, department_id) VALUES
    ('Программирование на Python',                1),
    ('Алгоритмы и структуры данных',              1),
    ('Объектно-ориентированное программирование', 1),
    ('Базы данных',                               2),
    ('Веб-разработка',                            2),
    ('Экономическая теория',                      3),
    ('Микроэкономика',                            3),
    ('Основы менеджмента',                        4),
    ('Маркетинг',                                 4),
    ('Математический анализ',                     5),
    ('Линейная алгебра',                          5),
    ('Дискретная математика',                     5),
    ('Общая физика',                              6),
    ('Механика',                                  6),
    ('История России',                            7),
    ('Всемирная история',                         7),
    ('Английский язык',                           8),
    ('Немецкий язык',                             8);

INSERT INTO student_groups (group_name, faculty_id)
SELECT
    'Группа-' || lpad(i::text, 3, '0'),
    ((i - 1) / 13) + 1
FROM generate_series(1, 50) AS i;

INSERT INTO teachers (full_name, department_id, password, passport_data)
SELECT
    'Преподаватель_' || i,
    ((i - 1) % 8) + 1,
    substring(md5(random()::text), 1, 8),
    lpad((floor(random() * 10000000000))::text, 10, '0')
FROM generate_series(1, 500) AS i;

INSERT INTO teacher_subjects (teacher_id, subject_id)
SELECT t.id, s.id
FROM teachers t
CROSS JOIN LATERAL (
    SELECT id FROM subjects
    WHERE department_id = t.department_id
    ORDER BY random()
    LIMIT 2
) AS s;

CREATE TEMP TABLE tmp_students (id SERIAL, group_id INT);

INSERT INTO tmp_students (group_id)
SELECT ((i - 1) / 20) + 1
FROM generate_series(1, 1000) AS i;

INSERT INTO grades (group_id, subject, grade, semester, password, passport_data)
SELECT
    ts.group_id,
    s.name,
    floor(random() * 4 + 2)::int,
    1,
    substring(md5(random()::text), 1, 8),
    lpad((floor(random() * 10000000000))::text, 10, '0')
FROM tmp_students ts
CROSS JOIN LATERAL (
    SELECT name FROM subjects
    ORDER BY random() + ts.id * 0
    LIMIT 10
) AS s;

DROP TABLE tmp_students;

INSERT INTO applications (program_name, application_year, status)
SELECT
    CASE (i % 3)
        WHEN 0 THEN 'Экономика'
        WHEN 1 THEN 'Прикладная информатика'
        ELSE 'Нефтегазовое дело'
    END,
    2022 + ((i - 1) / 300),
    CASE WHEN random() < 0.7 THEN 'подано' ELSE 'зачислен' END
FROM generate_series(1, 1500) AS i;

-- ============================================================
-- app_user + права
-- ============================================================

DROP USER IF EXISTS app_user;
CREATE USER app_user WITH PASSWORD 'secure_password_123';

GRANT CONNECT ON DATABASE university_db TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

ALTER ROLE app_user SET statement_timeout = '5s';

GRANT SELECT (id, name)                                         ON faculties        TO app_user;
GRANT SELECT (id, name, faculty_id)                             ON departments      TO app_user;
GRANT SELECT (id, full_name, department_id, password)           ON teachers         TO app_user;
GRANT SELECT (id, name, department_id)                          ON subjects         TO app_user;
GRANT SELECT (teacher_id, subject_id)                           ON teacher_subjects TO app_user;
GRANT SELECT (id, group_name, faculty_id)                       ON student_groups   TO app_user;
GRANT SELECT (id, program_name, application_year, status)       ON applications     TO app_user;
GRANT SELECT (id, group_id, subject, grade, semester, password) ON grades           TO app_user;