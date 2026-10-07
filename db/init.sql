-- Полный скрипт инициализации, генерации данных и настройки безопасности

-- 0. Устанавливаем ограничение времени выполнения запроса (защита от зависания/DDoS)
ALTER DATABASE university_db SET statement_timeout = '5s';

-- 1. Удаляем таблицы, если они существовали (для чистого перезапуска)
DROP TABLE IF EXISTS grades CASCADE;
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS student_groups CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS faculties CASCADE;

-- 2. Факультеты
CREATE TABLE faculties (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- 3. Преподаватели (с полями для пароля и паспорта)
CREATE TABLE teachers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    password VARCHAR(255),
    passport_data VARCHAR(100)
);

-- 4. Студенческие группы
CREATE TABLE student_groups (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(50) NOT NULL,
    faculty_id INT REFERENCES faculties(id)
);

-- 5. Заявления абитуриентов
CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    program_name VARCHAR(100) NOT NULL,
    application_year INT NOT NULL,
    status VARCHAR(50)
);

-- 6. Оценки студентов (также добавили поля по условию задачи)
CREATE TABLE grades (
    id SERIAL PRIMARY KEY,
    group_id INT REFERENCES student_groups(id),
    subject VARCHAR(100) NOT NULL,
    grade INT CHECK (grade >= 2 AND grade <= 5),
    semester INT NOT NULL,
    password VARCHAR(255),
    passport_data VARCHAR(100)
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

-- 9. Генерируем 500 преподавателей (с генерацией пароля и 10-значного паспорта)
INSERT INTO teachers (full_name, department, password, passport_data)
SELECT 
    'Преподаватель_' || i,
    CASE (i % 5) 
        WHEN 0 THEN 'Высшая математика'
        WHEN 1 THEN 'Программирование'
        WHEN 2 THEN 'Базы данных'
        WHEN 3 THEN 'Экономика'
        ELSE 'Менеджмент'
    END,
    substring(md5(random()::text) from 1 for 8), -- случайный пароль на 8 символов
    lpad(floor(random() * 10000000000)::text, 10, '0') -- случайный паспорт из 10 цифр
FROM generate_series(1, 500) AS i;

-- 10. Создаем временную таблицу для 1000 студентов (по 20 на группу)
DROP TABLE IF EXISTS temp_students;
CREATE TEMP TABLE temp_students (id SERIAL, group_id INT);
INSERT INTO temp_students (group_id)
SELECT 
    ((i - 1) / 20) + 1 
FROM generate_series(1, 1000) AS i;

-- 11. Генерируем оценки для студентов (10 000 строк, заполняем пароли и паспорта)
INSERT INTO grades (group_id, subject, grade, semester, password, passport_data)
SELECT 
    ts.group_id,
    'Предмет_' || sub.subject_num,
    floor(random() * 4 + 2)::int,
    1,
    substring(md5(random()::text) from 1 for 8),
    lpad(floor(random() * 10000000000)::text, 10, '0')
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


-- 13. БЕЗОПАСНОСТЬ: Создание пользователя, ограничение таймаута и точечная выдача прав
CREATE USER app_user WITH PASSWORD 'secure_password_123';

GRANT CONNECT ON DATABASE university_db TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- Принудительно устанавливаем statement_timeout для конкретной роли app_user (на всякий случай)
ALTER ROLE app_user SET statement_timeout = '5s';

-- Выдаем права SELECT только на разрешенные колонки (исключая паспорта)
GRANT SELECT (id, name) ON faculties TO app_user;
GRANT SELECT (id, full_name, department, password) ON teachers TO app_user;
GRANT SELECT (id, group_name, faculty_id) ON student_groups TO app_user;
GRANT SELECT (id, program_name, application_year, status) ON applications TO app_user;
GRANT SELECT (id, group_id, subject, grade, semester, password) ON grades TO app_user;
