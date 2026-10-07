-- Полный скрипт инициализации и наполнения базы данных university_db

-- 1. Удаляем таблицы, если они существовали (для чистого перезапуска)
DROP TABLE IF EXISTS grades CASCADE;
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS student_groups CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS faculties CASCADE;
ALTER DATABASE university_db SET statement_timeout = '5s';
-- 2. Факультеты
CREATE TABLE faculties (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- 3. Преподаватели (их ФИО можно выводить по условиям кейса)
CREATE TABLE teachers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL
);

-- 4. Студенческие группы
CREATE TABLE student_groups (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(50) NOT NULL,
    faculty_id INT REFERENCES faculties(id)
);

-- 5. Заявления абитуриентов (для сценариев приемной комиссии)
CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    program_name VARCHAR(100) NOT NULL,
    application_year INT NOT NULL,
    status VARCHAR(50)
);

-- 6. Оценки студентов (храним обезличенно)
CREATE TABLE grades (
    id SERIAL PRIMARY KEY,
    group_id INT REFERENCES student_groups(id),
    subject VARCHAR(100) NOT NULL,
    grade INT CHECK (grade >= 2 AND grade <= 5),
    semester INT NOT NULL
);

-- 7. Создание 2 факультетов
INSERT INTO faculties (name) VALUES 
('Факультет информационных технологий'),
('Факультет экономики и управления');

-- 8. Генерируем 50 групп
INSERT INTO student_groups (group_name, faculty_id)
SELECT 
    'Группа-' || lpad(i::text, 3, '0'),
    (i % 2) + 1 
FROM generate_series(1, 50) AS i;

-- 9. Генерируем 500 преподавателей
INSERT INTO teachers (full_name, department)
SELECT 
    'Преподаватель_' || i,
    CASE (i % 5) 
        WHEN 0 THEN 'Высшая математика'
        WHEN 1 THEN 'Программирование'
        WHEN 2 THEN 'Базы данных'
        WHEN 3 THEN 'Экономика'
        ELSE 'Менеджмент'
    END
FROM generate_series(1, 500) AS i;

-- 10. Создаем временную таблицу для 1000 студентов (по 20 на группу)
CREATE TEMP TABLE temp_students (id SERIAL, group_id INT);
INSERT INTO temp_students (group_id)
SELECT 
    ((i - 1) / 20) + 1 
FROM generate_series(1, 1000) AS i;

-- 11. Генерируем оценки для студентов (10 000 строк)
INSERT INTO grades (group_id, subject, grade, semester)
SELECT 
    ts.group_id,
    'Предмет_' || sub.subject_num,
    floor(random() * 4 + 2)::int,
    1 
FROM temp_students ts
CROSS JOIN generate_series(1, 10) AS sub(subject_num);

-- Удаляем временную таблицу
DROP TABLE temp_students;

-- 12. Добавляем заявления для приемной комиссии
INSERT INTO applications (program_name, application_year, status)
SELECT 
    CASE (i % 3) 
        WHEN 0 THEN 'Экономика'
        WHEN 1 THEN 'Прикладная информатика'
        ELSE 'Нефтегазовое дело'
    END,
    2026,
    'подано'
FROM generate_series(1, 450) AS i;


-- 13. Создание пользователя для бэкенда и выдача прав
CREATE USER app_user WITH PASSWORD 'secure_password_123';
GRANT CONNECT ON DATABASE university_db TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT ON faculties, teachers, student_groups, applications, grades TO app_user;