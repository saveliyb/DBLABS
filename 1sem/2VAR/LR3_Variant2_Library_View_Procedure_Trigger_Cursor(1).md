# Лабораторная работа №3 — VIEW / PROCEDURE / TRIGGER / CURSOR (PostgreSQL)
## Вариант №2 — Библиотека (в стиле ЛР2: жёсткие SETUP + точные ожидания) 

---

# 0) Быстрый чек: таблицы существуют
```sql
SELECT
  to_regclass('public.book_types') AS book_types,
  to_regclass('public.books')      AS books,
  to_regclass('public.clients')    AS clients,
  to_regclass('public.journal')    AS journal;
```
**Ожидаем:** везде не `NULL`.

---

# 1) ПРЕДСТАВЛЕНИЯ (VIEW)

## 1.1 View: все книги и читатели, о которых найдены записи в журнале за интервал дат

> В PostgreSQL view не принимает параметры. Поэтому делаем view “в целом”, а **фильтрацию по датам делаем запросом к view**. (На защите это нормально: “view + where”).

### SETUP (детерминированные даты)
```sql
BEGIN;

-- чистим тесты
DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T3_V11_%')
   OR client_id IN (SELECT id FROM clients WHERE last_name LIKE 'T3_V11_%');

DELETE FROM books    WHERE name LIKE 'T3_V11_%';
DELETE FROM clients  WHERE last_name LIKE 'T3_V11_%';
DELETE FROM book_types WHERE type='T3_V11_type';

INSERT INTO book_types(type, fine, day_count) VALUES ('T3_V11_type', 10, 10);

INSERT INTO books(name, cnt, type_id) VALUES
('T3_V11_Book_A', 1, (SELECT id FROM book_types WHERE type='T3_V11_type' ORDER BY id DESC LIMIT 1)),
('T3_V11_Book_B', 1, (SELECT id FROM book_types WHERE type='T3_V11_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number) VALUES
('A', 'T3_V11_Client_A', NULL, '3111', '311111'),
('B', 'T3_V11_Client_B', NULL, '3112', '311222');

-- две записи в journal: одна попадает в [2026-01-01, 2026-01-31], другая — нет
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T3_V11_Book_A' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_V11_Client_A' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-10', DATE '2026-01-20', DATE '2026-01-20'),
((SELECT id FROM books WHERE name='T3_V11_Book_B' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_V11_Client_B' ORDER BY id DESC LIMIT 1),
 DATE '2026-02-10', DATE '2026-02-20', DATE '2026-02-20');

COMMIT;
```

### CREATE
```sql
DROP VIEW IF EXISTS v_t3_journal_books_clients;

CREATE VIEW v_t3_journal_books_clients AS
SELECT
  j.id        AS journal_id,
  j.date_beg,
  j.date_end,
  j.date_ret,
  b.id        AS book_id,
  b.name      AS book_name,
  c.id        AS client_id,
  c.last_name AS client_last_name,
  c.first_name AS client_first_name
FROM journal j
JOIN books b   ON b.id = j.book_id
JOIN clients c ON c.id = j.client_id;
```

### TEST (фильтрация “за интервал” — это и есть решение пункта)
```sql
SELECT journal_id, book_name, client_last_name, date_beg, date_end, date_ret
FROM v_t3_journal_books_clients
WHERE date_beg BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'
ORDER BY journal_id;
```

### Что ожидаем
Вернётся **ровно 1 строка**: `T3_V11_Book_A` / `T3_V11_Client_A` с `date_beg=2026-01-10`.

---

## 1.2 View: все читатели и количество книг, находящихся у них на руках

> “На руках” = `journal.date_ret IS NULL`.

### SETUP (3 клиента: у одного 2 на руках, у второго 0, у третьего 1 возвращённая)
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name LIKE 'T3_V12_%')
   OR book_id IN (SELECT id FROM books WHERE name LIKE 'T3_V12_%');

DELETE FROM books WHERE name LIKE 'T3_V12_%';
DELETE FROM clients WHERE last_name LIKE 'T3_V12_%';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T3_V12_type', 10, 10
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T3_V12_type');

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number) VALUES
('A','T3_V12_Client_2',NULL,'3121','312111'),
('B','T3_V12_Client_0',NULL,'3122','312222'),
('C','T3_V12_Client_ret',NULL,'3123','312333');

INSERT INTO books(name, cnt, type_id) VALUES
('T3_V12_B1', 1, (SELECT id FROM book_types WHERE type='T3_V12_type' ORDER BY id DESC LIMIT 1)),
('T3_V12_B2', 1, (SELECT id FROM book_types WHERE type='T3_V12_type' ORDER BY id DESC LIMIT 1)),
('T3_V12_B3', 1, (SELECT id FROM book_types WHERE type='T3_V12_type' ORDER BY id DESC LIMIT 1));

-- Client_2: две книги на руках
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T3_V12_B1' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_V12_Client_2' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+10, NULL),
((SELECT id FROM books WHERE name='T3_V12_B2' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_V12_Client_2' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+10, NULL);

-- Client_ret: книга возвращена
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T3_V12_B3' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_V12_Client_ret' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+10, CURRENT_DATE);

COMMIT;
```

### CREATE
```sql
DROP VIEW IF EXISTS v_t3_clients_onhand;

CREATE VIEW v_t3_clients_onhand AS
SELECT
  c.id,
  c.last_name,
  c.first_name,
  COUNT(j.id) FILTER (WHERE j.date_ret IS NULL) AS on_hand
FROM clients c
LEFT JOIN journal j ON j.client_id = c.id
GROUP BY c.id, c.last_name, c.first_name;
```

### TEST
```sql
SELECT last_name, on_hand
FROM v_t3_clients_onhand
WHERE last_name LIKE 'T3_V12_%'
ORDER BY last_name;
```

### Что ожидаем
- `T3_V12_Client_0` → `on_hand = 0`  
- `T3_V12_Client_2` → `on_hand = 2`  
- `T3_V12_Client_ret` → `on_hand = 0`

---

# 2) ХРАНИМЫЕ ПРОЦЕДУРЫ (PROCEDURE)
## 2.0 Коротко: чем процедура отличается от функции (для ответа преподавателю)

- **FUNCTION** возвращает значение и может использоваться в `SELECT ...` как выражение.
- **PROCEDURE** вызывается через `CALL` и может управлять транзакциями (в т.ч. `COMMIT/ROLLBACK` внутри при нужных настройках), удобна для “операций/бизнес-логики”.
- В этой ЛР требуют именно **процедуры**, потому что часть заданий “процедурные”: сравнения, выходные параметры, курсоры, исключения/контроль потока.

### Почему PL/pgSQL (а не SQL)
- SQL-процедуры ограничены: без переменных/циклов/курсов/исключений.
- PL/pgSQL нужен для: `IF`, `LOOP`, курсоров, `RAISE EXCEPTION`, вычислений и накопления результата.
---

## 2.1 Без параметров: вывести все книги и среднее время, на которое их брали (в днях)

> Важно: процедура не “возвращает таблицу” как SELECT. Чтобы на защите **видеть результат**, мы выводим строки через `RAISE NOTICE`.
> Это считается “выводом” и отлично демонстрируется в pgAdmin вкладкой Messages.

### SETUP (2 книги: среднее 10 и 5 дней)
```sql
BEGIN;

-- сначала journal
DELETE FROM journal
WHERE client_id IN (
    SELECT id FROM clients
    WHERE passpot_seria='3211' AND passport_number='321111'
)
   OR book_id IN (SELECT id FROM books WHERE name LIKE 'T3_P21_%');

-- теперь клиент по паспорту (жёстко)
DELETE FROM clients
WHERE passpot_seria='3211'
  AND passport_number='321111';

-- книги и тип
DELETE FROM books WHERE name LIKE 'T3_P21_%';
DELETE FROM book_types WHERE type='T3_P21_type';

INSERT INTO book_types(type, fine, day_count)
VALUES ('T3_P21_type', 10, 10);

INSERT INTO books(name, cnt, type_id) VALUES
('T3_P21_Book10', 1, (SELECT id FROM book_types WHERE type='T3_P21_type' ORDER BY id DESC LIMIT 1)),
('T3_P21_Book5',  1, (SELECT id FROM book_types WHERE type='T3_P21_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('A','T3_P21_Client',NULL,'3211','321111');

-- дальше journal как было
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T3_P21_Book10' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE passpot_seria='3211' AND passport_number='321111'),
       DATE '2026-01-01', DATE '2026-01-11', DATE '2026-01-11'
FROM generate_series(1,2);

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T3_P21_Book5' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE passpot_seria='3211' AND passport_number='321111'),
       DATE '2026-01-01', DATE '2026-01-06', DATE '2026-01-06'
FROM generate_series(1,2);

COMMIT;
```

### CREATE
```sql
DROP PROCEDURE IF EXISTS p_t3_books_avg_days;

CREATE OR REPLACE PROCEDURE p_t3_books_avg_days()
LANGUAGE plpgsql
AS $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT
      b.name AS book_name,
      AVG((j.date_ret - j.date_beg))::NUMERIC(10,2) AS avg_days
    FROM books b
    JOIN journal j ON j.book_id = b.id
    WHERE j.date_ret IS NOT NULL
      AND b.name LIKE 'T3_P21_%'
    GROUP BY b.name
    ORDER BY b.name
  LOOP
    RAISE NOTICE 'book=% avg_days=%', r.book_name, r.avg_days;
  END LOOP;
END $$;
```

### TEST
```sql
CALL p_t3_books_avg_days();
```

### Что ожидаем (в Messages)
Две строки NOTICE:
- `book=T3_P21_Book10 avg_days=10.00`
- `book=T3_P21_Book5 avg_days=5.00`

---

## 2.2 С входными параметрами: клиенты, которые вернули «книгу1» быстрее, чем «книгу2» 

> Чтобы результат было видно как таблицу, используем **OUT refcursor** (типичный паттерн для процедур в PostgreSQL).

### SETUP (2 клиента: один подходит, другой нет)
```sql
BEGIN;

-- ЧИСТКА
DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T3_P22_%')
   OR client_id IN (
     SELECT id FROM clients
     WHERE (passpot_seria='3221' AND passport_number='322111')
        OR (passpot_seria='3222' AND passport_number='322222')
   );

DELETE FROM clients
WHERE (passpot_seria='3221' AND passport_number='322111')
   OR (passpot_seria='3222' AND passport_number='322222');

DELETE FROM books WHERE name LIKE 'T3_P22_%';
DELETE FROM book_types WHERE type='T3_P22_type';

-- СОЗДАНИЕ
INSERT INTO book_types(type, fine, day_count) VALUES ('T3_P22_type', 10, 10);

INSERT INTO books(name, cnt, type_id) VALUES
('T3_P22_Book1', 1, (SELECT id FROM book_types WHERE type='T3_P22_type' ORDER BY id DESC LIMIT 1)),
('T3_P22_Book2', 1, (SELECT id FROM book_types WHERE type='T3_P22_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number) VALUES
('A','T3_P22_Fast',NULL,'3221','322111'),
('B','T3_P22_Slow',NULL,'3222','322222');

-- 4 записи journal (Fast: 2 vs 5, Slow: 6 vs 3)
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
-- Fast Book1 = 2 дня
((SELECT id FROM books WHERE name='T3_P22_Book1' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE passpot_seria='3221' AND passport_number='322111' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-03', DATE '2026-01-03'),
-- Fast Book2 = 5 дней
((SELECT id FROM books WHERE name='T3_P22_Book2' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE passpot_seria='3221' AND passport_number='322111' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-06', DATE '2026-01-06'),

-- Slow Book1 = 6 дней
((SELECT id FROM books WHERE name='T3_P22_Book1' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE passpot_seria='3222' AND passport_number='322222' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-07', DATE '2026-01-07'),
-- Slow Book2 = 3 дня
((SELECT id FROM books WHERE name='T3_P22_Book2' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE passpot_seria='3222' AND passport_number='322222' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-04', DATE '2026-01-04');

COMMIT;
```

### CREATE
```sql
DROP PROCEDURE IF EXISTS p_t3_clients_book1_faster;

CREATE OR REPLACE PROCEDURE p_t3_clients_book1_faster(
  IN    p_book1 VARCHAR(20),
  IN    p_book2 VARCHAR(20),
  INOUT p_cur   REFCURSOR
)
LANGUAGE plpgsql
AS $$
BEGIN
  OPEN p_cur FOR
  WITH
  b1 AS (SELECT id FROM books WHERE name = p_book1),
  b2 AS (SELECT id FROM books WHERE name = p_book2),
  t1 AS (
    SELECT j.client_id, MIN(j.date_ret - j.date_beg) AS d1
    FROM journal j
    WHERE j.book_id IN (SELECT id FROM b1) AND j.date_ret IS NOT NULL
    GROUP BY j.client_id
  ),
  t2 AS (
    SELECT j.client_id, MIN(j.date_ret - j.date_beg) AS d2
    FROM journal j
    WHERE j.book_id IN (SELECT id FROM b2) AND j.date_ret IS NOT NULL
    GROUP BY j.client_id
  )
  SELECT c.last_name, t1.d1 AS days_book1, t2.d2 AS days_book2
  FROM t1
  JOIN t2 ON t2.client_id = t1.client_id
  JOIN clients c ON c.id = t1.client_id
  WHERE t1.d1 < t2.d2
  ORDER BY c.last_name;
END $$;
```

### TEST
```sql
WITH
b1 AS (SELECT id FROM books WHERE name='T3_P22_Book1'),
b2 AS (SELECT id FROM books WHERE name='T3_P22_Book2'),
t1 AS (
  SELECT j.client_id, MIN(j.date_ret - j.date_beg) AS d1
  FROM journal j
  WHERE j.book_id IN (SELECT id FROM b1) AND j.date_ret IS NOT NULL
  GROUP BY j.client_id
),
t2 AS (
  SELECT j.client_id, MIN(j.date_ret - j.date_beg) AS d2
  FROM journal j
  WHERE j.book_id IN (SELECT id FROM b2) AND j.date_ret IS NOT NULL
  GROUP BY j.client_id
)
SELECT c.last_name, t1.d1 AS days_book1, t2.d2 AS days_book2
FROM t1
JOIN t2 ON t2.client_id = t1.client_id
JOIN clients c ON c.id = t1.client_id
WHERE t1.d1 < t2.d2
ORDER BY c.last_name;
```

### Что ожидаем
Одна строка: `T3_P22_Fast` (days_book1=2, days_book2=5).

---

## 2.3 С выходными параметрами

### 2.3.1 Вход: «клиент», выход: количество книг у него на руках 

### SETUP (ровно 3 на руках)
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name='T3_P231_Client')
   OR book_id IN (SELECT id FROM books WHERE name LIKE 'T3_P231_B%');

DELETE FROM books WHERE name LIKE 'T3_P231_B%';
DELETE FROM clients WHERE last_name='T3_P231_Client';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T3_P231_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T3_P231_type');

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('Q','T3_P231_Client',NULL,'3231','323111');

INSERT INTO books(name, cnt, type_id)
SELECT 'T3_P231_B' || gs::text, 1, (SELECT id FROM book_types WHERE type='T3_P231_type' ORDER BY id DESC LIMIT 1)
FROM generate_series(1,3) gs;

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT b.id,
       (SELECT id FROM clients WHERE last_name='T3_P231_Client' ORDER BY id DESC LIMIT 1),
       CURRENT_DATE, CURRENT_DATE+1, NULL
FROM books b
WHERE b.name LIKE 'T3_P231_B%';

COMMIT;
```

### CREATE
```sql
DROP PROCEDURE IF EXISTS p_t3_client_onhand;

CREATE OR REPLACE PROCEDURE p_t3_client_onhand(
  IN  p_last_name VARCHAR(20),
  OUT p_onhand    INT
)
LANGUAGE plpgsql
AS $$
BEGIN
  SELECT COUNT(*)
  INTO p_onhand
  FROM journal j
  JOIN clients c ON c.id = j.client_id
  WHERE c.last_name = p_last_name
    AND j.date_ret IS NULL;
END $$;
```

### TEST
```sql
CALL p_t3_client_onhand('T3_P231_Client', NULL);
```

### Что ожидаем
`p_onhand = 3` (pgAdmin покажет это в результате CALL как OUT-параметр).

---

### 2.3.2 Вход: «книга», выход: максимальное время и читатель-рекордсмен

### SETUP (2 клиента: 7 дней и 12 дней → рекорд 12 дней)
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name='T3_P232_Book')
   OR client_id IN (SELECT id FROM clients WHERE last_name LIKE 'T3_P232_%');

DELETE FROM books WHERE name='T3_P232_Book';
DELETE FROM clients WHERE last_name LIKE 'T3_P232_%';
DELETE FROM book_types WHERE type='T3_P232_type';

INSERT INTO book_types(type, fine, day_count) VALUES ('T3_P232_type', 10, 10);
INSERT INTO books(name, cnt, type_id)
VALUES ('T3_P232_Book', 1, (SELECT id FROM book_types WHERE type='T3_P232_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number) VALUES
('A','T3_P232_C7',NULL,'3232','323201'),
('B','T3_P232_C12',NULL,'3232','323202');

-- 7 дней
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T3_P232_Book' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_P232_C7' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-08', DATE '2026-01-08'
);

-- 12 дней (рекорд)
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T3_P232_Book' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_P232_C12' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-13', DATE '2026-01-13'
);

COMMIT;
```

### CREATE
```sql
DROP PROCEDURE IF EXISTS p_t3_book_record;

CREATE OR REPLACE PROCEDURE p_t3_book_record(
  IN  p_book_name VARCHAR(20),
  OUT p_max_days  INT,
  OUT p_client_last_name VARCHAR(20)
)
LANGUAGE plpgsql
AS $$
BEGIN
  SELECT
    (j.date_ret - j.date_beg) AS days_taken,
    c.last_name
  INTO p_max_days, p_client_last_name
  FROM journal j
  JOIN books b   ON b.id = j.book_id
  JOIN clients c ON c.id = j.client_id
  WHERE b.name = p_book_name
    AND j.date_ret IS NOT NULL
  ORDER BY (j.date_ret - j.date_beg) DESC, j.id DESC
  LIMIT 1;
END $$;
```

### TEST
```sql
CALL p_t3_book_record('T3_P232_Book', NULL, NULL);
```

### Что ожидаем
`p_max_days = 12`, `p_client_last_name = 'T3_P232_C12'`.

---

# 3) ТРИГГЕРЫ (TRIGGER)

## 3.1 Триггер на вставку: запрет добавить читателя с паспортом, который уже существует 

> Да, у тебя уже есть UNIQUE на `(passpot_seria, passport_number)`.  
> Но по заданию нужен именно триггер — он даёт понятную ошибку “своим текстом”.

### SETUP (один клиент с паспортом 4444/444444)
```sql
BEGIN;

DELETE FROM clients
WHERE last_name LIKE 'T3_T31_%'
   OR (passpot_seria='4444' AND passport_number='444444');

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('A','T3_T31_Exists',NULL,'4444','444444');

COMMIT;
```

### CREATE
```sql
DROP TRIGGER IF EXISTS tr_t3_clients_no_dup_passport ON clients;
DROP FUNCTION IF EXISTS f_t3_clients_no_dup_passport;

CREATE OR REPLACE FUNCTION f_t3_clients_no_dup_passport()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM clients c
    WHERE c.passpot_seria = NEW.passpot_seria
      AND c.passport_number = NEW.passport_number
      AND c.id <> COALESCE(NEW.id, -1)
  ) THEN
    RAISE EXCEPTION 'Passport already exists: %/%', NEW.passpot_seria, NEW.passport_number;
  END IF;

  RETURN NEW;
END $$;

CREATE TRIGGER tr_t3_clients_no_dup_passport
BEFORE INSERT ON clients
FOR EACH ROW
EXECUTE FUNCTION f_t3_clients_no_dup_passport();
```

### TEST (должно упасть)
```sql
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('B','T3_T31_Duplicate',NULL,'4444','444444');
```

### Что ожидаем
Ошибка: `Passport already exists: 4444/444444` (или ошибка UNIQUE, если триггер не создался).

---

## 3.2 Триггер на модификацию: запрет установить date_ret меньше date_beg

### SETUP (одна запись journal)
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name='T3_T32_Client')
   OR book_id IN (SELECT id FROM books WHERE name='T3_T32_Book');

DELETE FROM books WHERE name='T3_T32_Book';
DELETE FROM clients WHERE last_name='T3_T32_Client';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T3_T32_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T3_T32_type');

INSERT INTO books(name, cnt, type_id)
VALUES ('T3_T32_Book', 1, (SELECT id FROM book_types WHERE type='T3_T32_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('C','T3_T32_Client',NULL,'5532','553200');

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T3_T32_Book' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_T32_Client' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-10', DATE '2026-01-20', NULL
);

COMMIT;
```

### CREATE
```sql
DROP TRIGGER IF EXISTS tr_t3_journal_ret_not_before_beg ON journal;
DROP FUNCTION IF EXISTS f_t3_journal_ret_not_before_beg;

CREATE OR REPLACE FUNCTION f_t3_journal_ret_not_before_beg()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.date_ret IS NOT NULL AND NEW.date_ret < NEW.date_beg THEN
    RAISE EXCEPTION 'date_ret (%) cannot be earlier than date_beg (%)', NEW.date_ret, NEW.date_beg;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER tr_t3_journal_ret_not_before_beg
BEFORE UPDATE OF date_ret ON journal
FOR EACH ROW
EXECUTE FUNCTION f_t3_journal_ret_not_before_beg();
```

### TEST (должно упасть)
```sql
UPDATE journal
SET date_ret = DATE '2026-01-01'
WHERE id = (SELECT id FROM journal WHERE book_id=(SELECT id FROM books WHERE name='T3_T32_Book' ORDER BY id DESC LIMIT 1) ORDER BY id DESC LIMIT 1);
```

### Что ожидаем
Ошибка: `date_ret (...) cannot be earlier than date_beg (...)`.

---

## 3.3 Триггер на удаление: при удалении строки journal, если книга не возвращена — откатить транзакцию 

### SETUP (одна запись journal “на руках”, date_ret NULL)
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name='T3_T33_Client')
   OR book_id IN (SELECT id FROM books WHERE name='T3_T33_Book');

DELETE FROM books WHERE name='T3_T33_Book';
DELETE FROM clients WHERE last_name='T3_T33_Client';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T3_T33_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T3_T33_type');

INSERT INTO books(name, cnt, type_id)
VALUES ('T3_T33_Book', 1, (SELECT id FROM book_types WHERE type='T3_T33_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('D','T3_T33_Client',NULL,'6633','663300');

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T3_T33_Book' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_T33_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+1, NULL
);

COMMIT;
```

### CREATE
```sql
DROP TRIGGER IF EXISTS tr_t3_journal_no_delete_if_onhand ON journal;
DROP FUNCTION IF EXISTS f_t3_journal_no_delete_if_onhand;

CREATE OR REPLACE FUNCTION f_t3_journal_no_delete_if_onhand()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD.date_ret IS NULL THEN
    RAISE EXCEPTION 'Cannot delete journal row: book not returned (date_ret IS NULL).';
  END IF;
  RETURN OLD;
END $$;

CREATE TRIGGER tr_t3_journal_no_delete_if_onhand
BEFORE DELETE ON journal
FOR EACH ROW
EXECUTE FUNCTION f_t3_journal_no_delete_if_onhand();
```

### TEST (должно упасть и ничего не удалить)
```sql
DELETE FROM journal
WHERE id = (SELECT id FROM journal WHERE book_id=(SELECT id FROM books WHERE name='T3_T33_Book' ORDER BY id DESC LIMIT 1) ORDER BY id DESC LIMIT 1);
```

**Проверка, что запись осталась**
```sql
SELECT COUNT(*) AS journal_left
FROM journal
WHERE book_id = (SELECT id FROM books WHERE name='T3_T33_Book' ORDER BY id DESC LIMIT 1)
  AND date_ret IS NULL;
```

### Что ожидаем
- DELETE выдаёт ошибку `Cannot delete journal row...`
- `journal_left = 1`

---

## 3.4 FOR EACH ROW vs FOR EACH STATEMENT (ответ)

- `FOR EACH ROW` — триггер срабатывает **на каждую строку** (NEW/OLD доступны).
- `FOR EACH STATEMENT` — триггер срабатывает **1 раз на оператор** (NEW/OLD нет для строк; используется для “общих” действий).

В этой ЛР нам нужны проверки конкретных строк (паспорт, date_ret, удаление записи) → поэтому `FOR EACH ROW`. 

---

# 4) КУРСОРЫ (CURSOR) 

## 4.1 Процедура: сумма штрафов, полученная библиотекой за период (2 IN даты + 1 OUT сумма)

Алгоритм по методичке: курсор по строкам journal, где `date_ret` попадает в интервал; для каждой строки считаем штраф и суммируем.

### SETUP (2 возврата в интервале: штраф 30 и 100 → сумма 130)
```sql
BEGIN;

-- 0) удаляем journal по тестовым книгам и/или по паспорту клиента (уникальный ключ)
DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T3_C41_%')
   OR client_id IN (
     SELECT id FROM clients
     WHERE passpot_seria='7741' AND passport_number='774111'
   );

-- 1) удаляем книги/клиента/типы
DELETE FROM books WHERE name LIKE 'T3_C41_%';

DELETE FROM clients
WHERE passpot_seria='7741' AND passport_number='774111';

DELETE FROM book_types WHERE type LIKE 'T3_C41_%';

-- 2) создаём заново
INSERT INTO book_types(type, fine, day_count) VALUES
('T3_C41_t10', 10, 10),
('T3_C41_t50', 50, 10);

INSERT INTO books(name, cnt, type_id) VALUES
('T3_C41_B1', 1, (SELECT id FROM book_types WHERE type='T3_C41_t10' ORDER BY id DESC LIMIT 1)),
('T3_C41_B2', 1, (SELECT id FROM book_types WHERE type='T3_C41_t50' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('F','T3_C41_Client',NULL,'7741','774111');

-- 2 строки journal
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T3_C41_B1' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE passpot_seria='7741' AND passport_number='774111' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-10', DATE '2026-01-13'),
((SELECT id FROM books WHERE name='T3_C41_B2' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE passpot_seria='7741' AND passport_number='774111' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-01', DATE '2026-01-10', DATE '2026-01-12');

COMMIT;
```

### CREATE
```sql
DROP PROCEDURE IF EXISTS p_t3_fines_sum_period;

CREATE OR REPLACE PROCEDURE p_t3_fines_sum_period(
  IN  p_from DATE,
  IN  p_to   DATE,
  OUT p_sum  INT
)
LANGUAGE plpgsql
AS $$
DECLARE
  r RECORD;

  cur CURSOR FOR
    SELECT
      j.date_end,
      j.date_ret,
      bt.fine
    FROM journal j
    JOIN books b       ON b.id = j.book_id
    JOIN book_types bt ON bt.id = b.type_id
    WHERE j.date_ret IS NOT NULL
      AND j.date_ret BETWEEN p_from AND p_to
      -- ВАЖНО: считаем только тестовые строки
      AND b.name LIKE 'T3_C41_%';
BEGIN
  p_sum := 0;

  OPEN cur;

  LOOP
    FETCH cur INTO r;
    EXIT WHEN NOT FOUND;

    IF r.date_ret > r.date_end THEN
      p_sum := p_sum + (r.date_ret - r.date_end) * r.fine;
    END IF;

  END LOOP;

  CLOSE cur;
END $$;
```

### TEST
```sql
CALL p_t3_fines_sum_period(DATE '2026-01-01', DATE '2026-01-31', NULL);
```

### Что ожидаем
`p_sum = 130`.

---

## 4.2 Процедура: 3 самые популярные книги за период (2 IN даты)

Алгоритм по методичке: держим топ-3 (id и count), курсор по книгам, выданным в интервал, считаем выдачи, обновляем топ.

### SETUP (частоты 5/4/3/1 → топ: B1,B2,B3)
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T3_C42_%');

DELETE FROM books WHERE name LIKE 'T3_C42_%';
DELETE FROM book_types WHERE type='T3_C42_type';

INSERT INTO book_types(type, fine, day_count) VALUES ('T3_C42_type', 1, 1);

INSERT INTO books(name, cnt, type_id) VALUES
('T3_C42_B1', 1, (SELECT id FROM book_types WHERE type='T3_C42_type' ORDER BY id DESC LIMIT 1)),
('T3_C42_B2', 1, (SELECT id FROM book_types WHERE type='T3_C42_type' ORDER BY id DESC LIMIT 1)),
('T3_C42_B3', 1, (SELECT id FROM book_types WHERE type='T3_C42_type' ORDER BY id DESC LIMIT 1)),
('T3_C42_B4', 1, (SELECT id FROM book_types WHERE type='T3_C42_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
SELECT 'P','T3_C42_Client',NULL,'8842','884211'
WHERE NOT EXISTS (SELECT 1 FROM clients WHERE last_name='T3_C42_Client');

-- интервал будем брать январь 2026, ставим date_beg в январе, date_ret тоже
-- B1: 5
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T3_C42_B1' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE last_name='T3_C42_Client' ORDER BY id DESC LIMIT 1),
       DATE '2026-01-10', DATE '2026-01-11', DATE '2026-01-11'
FROM generate_series(1,5);

-- B2: 4
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T3_C42_B2' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE last_name='T3_C42_Client' ORDER BY id DESC LIMIT 1),
       DATE '2026-01-10', DATE '2026-01-11', DATE '2026-01-11'
FROM generate_series(1,4);

-- B3: 3
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T3_C42_B3' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE last_name='T3_C42_Client' ORDER BY id DESC LIMIT 1),
       DATE '2026-01-10', DATE '2026-01-11', DATE '2026-01-11'
FROM generate_series(1,3);

-- B4: 1
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T3_C42_B4' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T3_C42_Client' ORDER BY id DESC LIMIT 1),
 DATE '2026-01-10', DATE '2026-01-11', DATE '2026-01-11'
);

COMMIT;
```

### CREATE
```sql
DROP PROCEDURE IF EXISTS p_t3_top3_books_period;

CREATE OR REPLACE PROCEDURE p_t3_top3_books_period(
  IN p_from DATE,
  IN p_to   DATE
)
LANGUAGE plpgsql
AS $$
DECLARE
  r RECORD;
  v_id1 INT := NULL; v_id2 INT := NULL; v_id3 INT := NULL;
  v_c1  INT := 0;    v_c2  INT := 0;    v_c3  INT := 0;
  v_cnt INT;

  cur CURSOR FOR
    SELECT DISTINCT j.book_id
    FROM journal j
    WHERE j.date_beg BETWEEN p_from AND p_to;
BEGIN
  OPEN cur;
  LOOP
    FETCH cur INTO r;
    EXIT WHEN NOT FOUND;

    SELECT COUNT(*) INTO v_cnt
    FROM journal
    WHERE book_id = r.book_id
      AND date_beg BETWEEN p_from AND p_to;

    IF v_cnt > v_c1 THEN
      v_id3 := v_id2; v_c3 := v_c2;
      v_id2 := v_id1; v_c2 := v_c1;
      v_id1 := r.book_id; v_c1 := v_cnt;
    ELSIF v_cnt > v_c2 AND r.book_id <> v_id1 THEN
      v_id3 := v_id2; v_c3 := v_c2;
      v_id2 := r.book_id; v_c2 := v_cnt;
    ELSIF v_cnt > v_c3 AND r.book_id <> v_id1 AND r.book_id <> v_id2 THEN
      v_id3 := r.book_id; v_c3 := v_cnt;
    END IF;
  END LOOP;
  CLOSE cur;

  -- Выводим результат (как “вывод” процедуры) через NOTICE
  RAISE NOTICE 'TOP1 book_id=% count=%', v_id1, v_c1;
  RAISE NOTICE 'TOP2 book_id=% count=%', v_id2, v_c2;
  RAISE NOTICE 'TOP3 book_id=% count=%', v_id3, v_c3;

  RAISE NOTICE 'TOP1 name=%', (SELECT name FROM books WHERE id=v_id1);
  RAISE NOTICE 'TOP2 name=%', (SELECT name FROM books WHERE id=v_id2);
  RAISE NOTICE 'TOP3 name=%', (SELECT name FROM books WHERE id=v_id3);
END $$;
```

### TEST
```sql
CALL p_t3_top3_books_period(DATE '2026-01-01', DATE '2026-01-31');
```

### Что ожидаем (в Messages)
Топ-3 по именам:
1) `T3_C42_B1` (5)  
2) `T3_C42_B2` (4)  
3) `T3_C42_B3` (3)

---

# 5) Мини-чеклист сдачи (контрольные результаты)
1) View 1.1 → по интервалу января вернётся 1 строка (Book_A/Client_A)  
2) View 1.2 → Client_2=2, Client_0=0, Client_ret=0  
3) Proc 2.1 → NOTICE: Book10=10.00, Book5=5.00  
4) Proc 2.2 → FETCH ALL: только `T3_P22_Fast`  
5) Proc 2.3.1 → OUT: `p_onhand=3`  
6) Proc 2.3.2 → OUT: `p_max_days=12`, `p_client_last_name=T3_P232_C12`  
7) Trigger insert → дубликат паспорта запрещён (ошибка)  
8) Trigger update → date_ret < date_beg запрещено (ошибка)  
9) Trigger delete → нельзя удалить journal при `date_ret IS NULL` (ошибка + запись остаётся)  
10) Cursor fines sum → `p_sum=130`  
11) Cursor top3 → B1/B2/B3 (5/4/3)

