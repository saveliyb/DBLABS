# Лабораторная работа №1 — Создание базы данных (PostgreSQL)
## Вариант №2 — Автоматизация работы библиотеки fileciteturn0file0

Ты показал свою ER-диаграмму — я **переделал типы и имена колонок под методичку/диаграмму**:

### book_types
- `id integer`
- `type character varying(20)`
- `fine integer`
- `day_count integer`

### books
- `id integer`
- `name character varying(20)`
- `cnt integer`
- `type_id integer` (FK → `book_types.id`)

### clients
- `id integer`
- `first_name character varying(20)`
- `last_name character varying(20)`
- `father_name character varying(20)`
- `passpot_seria character varying(4)`  *(да, в методичке/диаграмме именно так)*
- `passport_number character varying(6)`

### journal
- `id integer`
- `book_id integer` (FK → `books.id`)
- `client_id integer` (FK → `clients.id`)
- `date_beg date`
- `date_end date`
- `date_ret date`

> ⚠️ Про автоинкремент  
> Если в методичке хотят именно `SERIAL` — используем `SERIAL`.  
> Это соответствует твоей диаграмме (id integer).  
> Если преподаватель допускает — можно заменить на `GENERATED AS IDENTITY`, но ниже — **SERIAL**, чтобы совпало.

Формат: **SETUP → EXECUTE → TEST → Что делает → Что ожидаем**  
Все тестовые данные помечены префиксом `T1_`, чтобы запускать много раз.

---

## 1) Создание таблиц (DDL)

### 1.1 book_types (типы книг) fileciteturn0file0

**EXECUTE**
```sql
CREATE TABLE IF NOT EXISTS book_types (
  id        SERIAL PRIMARY KEY,
  type      VARCHAR(20) NOT NULL UNIQUE,
  fine      INTEGER NOT NULL CHECK (fine >= 0),
  day_count INTEGER NOT NULL CHECK (day_count > 0)
);
```

**TEST (многоразово)**
```sql
-- чистим тестовые строки
DELETE FROM book_types WHERE type LIKE 'T1_%';

-- добавляем 3 типа с крайними значениями из методички
INSERT INTO book_types(type, fine, day_count) VALUES
('T1_обычная',    10, 60),
('T1_редкая',     50, 21),
('T1_уникальная', 300, 7);

SELECT * FROM book_types WHERE type LIKE 'T1_%' ORDER BY id;
```

**Ожидаем:** 3 строки.

---

### 1.2 books (книги) fileciteturn0file0

**EXECUTE**
```sql
CREATE TABLE IF NOT EXISTS books (
  id      SERIAL PRIMARY KEY,
  name    VARCHAR(20) NOT NULL,
  cnt     INTEGER NOT NULL CHECK (cnt >= 0),
  type_id INTEGER NOT NULL,
  CONSTRAINT fk_books_types
    FOREIGN KEY (type_id) REFERENCES book_types(id)
    ON DELETE CASCADE
);
```

**TEST**
```sql
BEGIN;

-- чистим тесты
DELETE FROM books WHERE name LIKE 'T1_%';

-- крайние случаи: cnt=0 и cnt большое
INSERT INTO books(name, cnt, type_id) VALUES
('T1_Book_Zero', 0,  (SELECT id FROM book_types WHERE type='T1_обычная'    ORDER BY id DESC LIMIT 1)),
('T1_Book_Many', 9999, (SELECT id FROM book_types WHERE type='T1_уникальная' ORDER BY id DESC LIMIT 1))
RETURNING id, name, cnt, type_id;

COMMIT;

SELECT * FROM books WHERE name LIKE 'T1_%' ORDER BY id;
```

**Ожидаем:** 2 строки; одна с `cnt=0`.

---

### 1.3 clients (читатели) fileciteturn0file0

**EXECUTE**
```sql
CREATE TABLE IF NOT EXISTS clients (
  id              SERIAL PRIMARY KEY,
  first_name      VARCHAR(20) NOT NULL,
  last_name       VARCHAR(20) NOT NULL,
  father_name     VARCHAR(20),
  passpot_seria   VARCHAR(4)  NOT NULL,
  passport_number VARCHAR(6)  NOT NULL,
  CONSTRAINT uq_clients_passport UNIQUE (passpot_seria, passport_number)
);
```

**TEST**
```sql
BEGIN;

DELETE FROM clients
WHERE last_name LIKE 'T1_%'
   OR (passpot_seria='1111' AND passport_number='222222');

-- нормальная вставка
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('Ivan', 'T1_Ivanov', 'Ivanovich', '1111', '222222')
RETURNING id;

-- крайний случай: тот же паспорт (должно упасть по UNIQUE)
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('Petr', 'T1_Petrov', NULL, '1111', '222222');

COMMIT;
```
```sql
ROLLBACK;
```

**Ожидаем:** первая вставка проходит; вторая падает по UNIQUE.

---

### 1.4 journal (журнал) fileciteturn0file0

**EXECUTE**
```sql
CREATE TABLE IF NOT EXISTS journal (
  id       SERIAL PRIMARY KEY,
  book_id  INTEGER NOT NULL,
  client_id INTEGER NOT NULL,
  date_beg DATE NOT NULL DEFAULT CURRENT_DATE,
  date_end DATE NOT NULL,
  date_ret DATE,

  CONSTRAINT fk_journal_books
    FOREIGN KEY (book_id) REFERENCES books(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_journal_clients
    FOREIGN KEY (client_id) REFERENCES clients(id)
    ON DELETE CASCADE,

  CONSTRAINT chk_ret_after_beg
    CHECK (date_ret IS NULL OR date_ret >= date_beg)
);
```

**TEST**
```sql
BEGIN;

-- чистим тестовые записи (через книги/клиентов)
DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T1_%')
   OR client_id IN (SELECT id FROM clients WHERE last_name LIKE 'T1_%');

-- вставим выдачу: date_end = date_beg + day_count типа книги
INSERT INTO journal(book_id, client_id, date_end)
VALUES (
  (SELECT id FROM books WHERE name='T1_Book_Many' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T1_Ivanov' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE + (SELECT day_count
                  FROM book_types
                  WHERE id = (SELECT type_id FROM books WHERE name='T1_Book_Many' ORDER BY id DESC LIMIT 1))
)
RETURNING id, date_beg, date_end, date_ret;

-- крайний случай: попытка вернуть раньше выдачи (должно упасть по CHECK)
UPDATE journal
SET date_ret = date_beg - INTERVAL '1 day'
WHERE id = (SELECT id FROM journal ORDER BY id DESC LIMIT 1);

COMMIT;
```
```sql
ROLLBACK;
```

**Ожидаем:** insert проходит; update падает по `chk_ret_after_beg`.

---

## 2) Проверка связей и каскадного удаления (ON DELETE CASCADE) fileciteturn0file0

**EXECUTE (одним блоком, чтобы ROLLBACK точно сработал)**
```sql
BEGIN;

-- до удаления типа
SELECT COUNT(*) AS books_unique_before
FROM books b
JOIN book_types bt ON bt.id=b.type_id
WHERE bt.type='T1_уникальная';

SELECT COUNT(*) AS journal_for_unique_before
FROM journal j
JOIN books b ON b.id=j.book_id
JOIN book_types bt ON bt.id=b.type_id
WHERE bt.type='T1_уникальная';

-- удаляем тип (должен каскадно удалить книги этого типа и записи journal на них)
DELETE FROM book_types WHERE type='T1_уникальная';

-- после удаления типа
SELECT COUNT(*) AS books_unique_after
FROM books b
JOIN book_types bt ON bt.id=b.type_id
WHERE bt.type='T1_уникальная';

-- проверка на “осиротевшие” записи журнала
SELECT COUNT(*) AS orphan_journal
FROM journal j
LEFT JOIN books b ON b.id=j.book_id
WHERE b.id IS NULL;

ROLLBACK;
```

**Ожидаем:** `books_unique_after = 0`, `orphan_journal = 0`. После `ROLLBACK` всё вернулось.

---

## 3) Backup → Drop DB → Restore fileciteturn0file0

### Вариант A (pgAdmin)
1) ПКМ по базе → **Backup…** (format: `custom`)  
2) **Drop…**  
3) Создать новую пустую базу  
4) ПКМ по базе → **Restore…**

### Вариант B (консоль)
```bash
pg_dump -Fc -h HOST -U USER -d DBNAME -f backup_lab1.dump
dropdb  -h HOST -U USER DBNAME
createdb -h HOST -U USER DBNAME
pg_restore -h HOST -U USER -d DBNAME backup_lab1.dump
```

**TEST после восстановления**
```sql
SELECT
  (SELECT COUNT(*) FROM book_types WHERE type LIKE 'T1_%') AS types_cnt,
  (SELECT COUNT(*) FROM books      WHERE name LIKE 'T1_%') AS books_cnt,
  (SELECT COUNT(*) FROM clients    WHERE last_name LIKE 'T1_%') AS clients_cnt,
  (SELECT COUNT(*) FROM journal) AS journal_cnt;
```

**Ожидаем:** данные на месте (как до backup).

---

## 4) Ответ на вопрос: `DELETE` vs `TRUNCATE` (коротко)
- `DELETE` можно с `WHERE`, построчно, триггеры `DELETE` срабатывают.
- `TRUNCATE` быстро очищает всю таблицу, без `WHERE`, с FK часто нужен `CASCADE`.

---

## 5) Ответ: `serial` vs `GENERATED AS IDENTITY`
- `serial` = sequence + `DEFAULT nextval(...)` (старый, но рабочий).
- `IDENTITY` = стандарт SQL, sequence “привязана” к колонке (предпочтительнее в новых схемах).
В этой ЛР оставили `SERIAL`, чтобы совпало с методичкой/диаграммой.

---

## 6) Мини-чеклист сдачи
1) Показать 4 таблицы + типы колонок.  
2) Показать 3 FK + `ON DELETE CASCADE`.  
3) Показать авто-ID (insert без id).  
4) Сделать backup/drop/restore.  
5) Ответить `serial vs identity`.

