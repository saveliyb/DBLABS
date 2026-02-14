# Лабораторная работа №2 — SQL-DML (PostgreSQL)
## Вариант №2 — Библиотека (как для «магазина»: жёсткие SETUP + точные ожидания)

Схема (как в твоей ЛР1/диаграмме):
- **book_types**(`id serial`, `type varchar(20)`, `fine integer`, `day_count integer`)
- **books**(`id serial`, `name varchar(20)`, `cnt integer`, `type_id integer` → book_types.id)
- **clients**(`id serial`, `first_name varchar(20)`, `last_name varchar(20)`, `father_name varchar(20)`, `passpot_seria varchar(4)`, `passport_number varchar(6)`)
- **journal**(`id serial`, `book_id integer` → books.id, `client_id integer` → clients.id, `date_beg date`, `date_end date`, `date_ret date`)

Формат каждого пункта: **SETUP → EXECUTE → TEST → Что ожидаем**  
Все тестовые данные помечены префиксом **`T2_`** и файл рассчитан на **многоразовый запуск**.

> ⚠️ ВАЖНО ПРО pgAdmin / Auto-commit  
> Все примеры с `ROLLBACK` **выполняй одним блоком** (одной кнопкой Execute), иначе при Auto-commit “откат” может не сработать.

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

# 1) ВЫБОРКА ДАННЫХ (SELECT)

## 1.1 Однотабличная выборка

### 1.1.1 Вывести все строки из журнала, дата возврата которых меньше некоторой даты

**SETUP (2 записи: одна должна попасть, другая нет)**
```sql
BEGIN;

-- чистим тесты
DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_Q111_%')
   OR client_id IN (SELECT id FROM clients WHERE last_name LIKE 'T2_Q111_%');

DELETE FROM books WHERE name LIKE 'T2_Q111_%';
DELETE FROM book_types WHERE type LIKE 'T2_Q111_%';
DELETE FROM clients WHERE last_name LIKE 'T2_Q111_%';

-- справочник
INSERT INTO book_types(type, fine, day_count) VALUES ('T2_Q111_type', 10, 30);

-- книга + клиент
INSERT INTO books(name, cnt, type_id)
VALUES ('T2_Q111_book', 5, (SELECT id FROM book_types WHERE type='T2_Q111_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('Ivan', 'T2_Q111_client', 'I', '1111', '111111');

-- Дата-фильтр: 2026-01-01
-- 1) Должна попасть: date_ret=2025-12-31 < 2026-01-01
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_Q111_book' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_Q111_client' ORDER BY id DESC LIMIT 1),
  DATE '2025-12-01',
  DATE '2025-12-10',
  DATE '2025-12-31'
);

-- 2) Не должна попасть: date_ret=2026-01-02 >= 2026-01-01
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_Q111_book' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_Q111_client' ORDER BY id DESC LIMIT 1),
  DATE '2025-12-05',
  DATE '2025-12-20',
  DATE '2026-01-02'
);

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT id, book_id, client_id, date_beg, date_end, date_ret
FROM journal
WHERE date_ret < DATE '2026-01-01'
  AND book_id IN (SELECT id FROM books WHERE name LIKE 'T2_Q111_%')
ORDER BY id;
```

**TEST (покажем обе строки для сравнения)**
```sql
SELECT id, date_ret
FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_Q111_%')
ORDER BY id;
```

**Что ожидаем:**  
- EXECUTE вернёт **ровно 1 строку** с `date_ret = 2025-12-31`.  
- В TEST видно 2 строки (`2025-12-31` и `2026-01-02`).

---

### 1.1.2 Посчитать количество книг, которых нет в наличии

**SETUP (ровно 2 книги: одна cnt=0, другая cnt=5)**
```sql
BEGIN;

DELETE FROM books WHERE name LIKE 'T2_Q112_%';

-- гарантируем наличие хотя бы одного типа
INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_Q112_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_Q112_type');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_Q112_zero', 0, (SELECT id FROM book_types WHERE type='T2_Q112_type' ORDER BY id DESC LIMIT 1)),
('T2_Q112_have', 5, (SELECT id FROM book_types WHERE type='T2_Q112_type' ORDER BY id DESC LIMIT 1));

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT COUNT(*) AS no_stock
FROM books
WHERE cnt = 0
  AND name LIKE 'T2_Q112_%';
```

**Что ожидаем:** `no_stock = 1`.

---

## 1.2 Выборка с подзапросами

### 1.2.1 Вывести все книги типа «уникальные», которые на руках у читателей

> “На руках” = есть запись в `journal` с `date_ret IS NULL`.

**SETUP (2 уникальные книги: одна на руках, одна возвращена)**
```sql
BEGIN;

-- чистим
DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_Q121_%')
   OR client_id IN (SELECT id FROM clients WHERE last_name LIKE 'T2_Q121_%');

DELETE FROM books WHERE name LIKE 'T2_Q121_%';
DELETE FROM clients WHERE last_name LIKE 'T2_Q121_%';
DELETE FROM book_types WHERE type LIKE 'T2_Q121_%';

-- уникальный тип
INSERT INTO book_types(type, fine, day_count) VALUES ('T2_Q121_unique', 300, 7);

-- 2 книги уникального типа
INSERT INTO books(name, cnt, type_id) VALUES
('T2_Q121_U_onhand',  3, (SELECT id FROM book_types WHERE type='T2_Q121_unique' ORDER BY id DESC LIMIT 1)),
('T2_Q121_U_returned',3, (SELECT id FROM book_types WHERE type='T2_Q121_unique' ORDER BY id DESC LIMIT 1));

-- клиент
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('P', 'T2_Q121_client', NULL, '0001', '000001');

-- 1) на руках (date_ret NULL)
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_Q121_U_onhand' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_Q121_client' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE,
  CURRENT_DATE + 7,
  NULL
);

-- 2) возвращена (date_ret NOT NULL)
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_Q121_U_returned' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_Q121_client' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE,
  CURRENT_DATE + 7,
  CURRENT_DATE
);

COMMIT;
```

**EXECUTE (решение — подзапросы)**
```sql
SELECT b.name
FROM books b
WHERE b.type_id IN (
    SELECT id FROM book_types WHERE type='T2_Q121_unique'
)
AND b.id IN (
    SELECT book_id FROM journal WHERE date_ret IS NULL
)
ORDER BY b.name;
```

**Что ожидаем:** вернётся **ровно 1 строка**: `T2_Q121_U_onhand`.

---

## 1.3 Соединение таблиц (JOIN)

### 1.3.1 Вывести журнал, читателей (включая не бравших), и книги (включая не выдававшихся)

Это задача на **FULL OUTER JOIN**: показать строки даже если:
- клиент без записей в journal,
- книга без записей в journal.

**SETUP (3 сущности: клиент без выдач, книга без выдач, и одна выдача)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_Q131_%')
   OR client_id IN (SELECT id FROM clients WHERE last_name LIKE 'T2_Q131_%');

DELETE FROM books WHERE name LIKE 'T2_Q131_%';
DELETE FROM clients WHERE last_name LIKE 'T2_Q131_%';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_Q131_type', 10, 10
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_Q131_type');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_Q131_Book_Issued',  1, (SELECT id FROM book_types WHERE type='T2_Q131_type' ORDER BY id DESC LIMIT 1)),
('T2_Q131_Book_Never',   1, (SELECT id FROM book_types WHERE type='T2_Q131_type' ORDER BY id DESC LIMIT 1));

-- фамилии укоротили!
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number) VALUES
('A', 'T2Q131_CI', NULL, '1311', '131111'),
('B', 'T2Q131_CN', NULL, '1312', '131222');

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_Q131_Book_Issued' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2Q131_CI' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE,
  CURRENT_DATE + 10,
  NULL
);

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  c.last_name,
  b.name AS book_name,
  j.id   AS journal_id,
  j.date_beg,
  j.date_end,
  j.date_ret
FROM clients c
FULL OUTER JOIN journal j ON j.client_id = c.id
FULL OUTER JOIN books  b ON b.id = j.book_id
WHERE (
  c.last_name LIKE 'T2_Q131_%'
  OR c.last_name LIKE 'T2Q131_%'
  OR b.name LIKE 'T2_Q131_%'
)
ORDER BY c.last_name NULLS LAST, b.name NULLS LAST, j.id NULLS LAST;
```

**Что ожидаем (минимум 3 строки):**
1) строка с `T2_Q131_Client_Issued` + `T2_Q131_Book_Issued` + `journal_id NOT NULL`  
2) строка с `T2_Q131_Client_Never` + `book_name = NULL` + `journal_id = NULL`  
3) строка с `last_name = NULL` + `T2_Q131_Book_Never` + `journal_id = NULL`

---

## 1.4 Для реализации проекта

### 1.4.1 Число книг на руках у заданного клиента

**SETUP (клиент с ровно 2 книгами на руках + 1 возвращённой)**
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name='T2_P141_Client')
   OR book_id IN (SELECT id FROM books WHERE name LIKE 'T2_P141_%');

DELETE FROM books WHERE name LIKE 'T2_P141_%';
DELETE FROM clients WHERE last_name='T2_P141_Client';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_P141_type', 5, 5
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_P141_type');

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('X','T2_P141_Client',NULL,'1411','141111');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_P141_B1', 1, (SELECT id FROM book_types WHERE type='T2_P141_type' ORDER BY id DESC LIMIT 1)),
('T2_P141_B2', 1, (SELECT id FROM book_types WHERE type='T2_P141_type' ORDER BY id DESC LIMIT 1)),
('T2_P141_B3', 1, (SELECT id FROM book_types WHERE type='T2_P141_type' ORDER BY id DESC LIMIT 1));

-- 2 на руках
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T2_P141_B1' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P141_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+5, NULL),
((SELECT id FROM books WHERE name='T2_P141_B2' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P141_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+5, NULL);

-- 1 возвращённая
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T2_P141_B3' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P141_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+5, CURRENT_DATE);

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT COUNT(*) AS on_hand
FROM journal j
WHERE j.client_id = (SELECT id FROM clients WHERE last_name='T2_P141_Client' ORDER BY id DESC LIMIT 1)
  AND j.date_ret IS NULL;
```

**Что ожидаем:** `on_hand = 2`.

---

### 1.4.2 Размер штрафа заданного клиента

> Штраф начисляется только если: `date_ret IS NULL` и `CURRENT_DATE > date_end`  
> Формула по записи: `(CURRENT_DATE - date_end) * fine`, где `fine` берём из типа книги.

**SETUP (2 просроченные на руках: 2 дня и 5 дней; fine=10)**
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name='T2_P142_Client')
   OR book_id IN (SELECT id FROM books WHERE name LIKE 'T2_P142_%');

DELETE FROM books WHERE name LIKE 'T2_P142_%';
DELETE FROM clients WHERE last_name='T2_P142_Client';
DELETE FROM book_types WHERE type='T2_P142_type';

INSERT INTO book_types(type, fine, day_count) VALUES ('T2_P142_type', 10, 10);

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('Y','T2_P142_Client',NULL,'1421','142111');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_P142_B1', 1, (SELECT id FROM book_types WHERE type='T2_P142_type' ORDER BY id DESC LIMIT 1)),
('T2_P142_B2', 1, (SELECT id FROM book_types WHERE type='T2_P142_type' ORDER BY id DESC LIMIT 1));

-- просрочка 2 дня
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T2_P142_B1' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P142_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE - 20,
 CURRENT_DATE - 2,
 NULL
);

-- просрочка 5 дней
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T2_P142_B2' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P142_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE - 20,
 CURRENT_DATE - 5,
 NULL
);

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  SUM( (CURRENT_DATE - j.date_end) * bt.fine ) AS fine_sum
FROM journal j
JOIN books b      ON b.id = j.book_id
JOIN book_types bt ON bt.id = b.type_id
WHERE j.client_id = (SELECT id FROM clients WHERE last_name='T2_P142_Client' ORDER BY id DESC LIMIT 1)
  AND j.date_ret IS NULL
  AND CURRENT_DATE > j.date_end;
```

**Что ожидаем:** штраф = `(2*10) + (5*10) = 70`.

---

### 1.4.3 Размер самого большого штрафа

> Берём **максимум по отдельной записи** (не по сумме клиента).

**SETUP (две записи: просрочка 3 дня fine=10 и просрочка 2 дня fine=50)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_P143_%');

DELETE FROM books WHERE name LIKE 'T2_P143_%';
DELETE FROM book_types WHERE type LIKE 'T2_P143_%';

INSERT INTO book_types(type, fine, day_count) VALUES
('T2_P143_t10', 10, 10),
('T2_P143_t50', 50, 10);

INSERT INTO books(name, cnt, type_id) VALUES
('T2_P143_B1', 1, (SELECT id FROM book_types WHERE type='T2_P143_t10' ORDER BY id DESC LIMIT 1)),
('T2_P143_B2', 1, (SELECT id FROM book_types WHERE type='T2_P143_t50' ORDER BY id DESC LIMIT 1));

-- клиента возьмём любого тестового/создадим
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
SELECT 'Z', 'T2_P143_Client', NULL, '1431', '143111'
WHERE NOT EXISTS (SELECT 1 FROM clients WHERE last_name='T2_P143_Client');

-- штраф 3*10 = 30
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T2_P143_B1' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P143_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE - 20,
 CURRENT_DATE - 3,
 NULL
);

-- штраф 2*50 = 100 (максимальный)
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T2_P143_B2' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P143_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE - 20,
 CURRENT_DATE - 2,
 NULL
);

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  MAX( (CURRENT_DATE - j.date_end) * bt.fine ) AS max_fine
FROM journal j
JOIN books b       ON b.id = j.book_id
JOIN book_types bt ON bt.id = b.type_id
WHERE j.date_ret IS NULL
  AND CURRENT_DATE > j.date_end
  AND b.name LIKE 'T2_P143_%';
```

**Что ожидаем:** `max_fine = 100`.

---

### 1.4.4 Три самые популярные книги

> Популярность = сколько раз книга фигурирует в journal (выдачи).

**SETUP (4 книги с частотами 5/4/3/1)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_P144_%');

DELETE FROM books WHERE name LIKE 'T2_P144_%';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_P144_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_P144_type');

-- 4 книги
INSERT INTO books(name, cnt, type_id) VALUES
('T2_P144_B1', 1, (SELECT id FROM book_types WHERE type='T2_P144_type' ORDER BY id DESC LIMIT 1)),
('T2_P144_B2', 1, (SELECT id FROM book_types WHERE type='T2_P144_type' ORDER BY id DESC LIMIT 1)),
('T2_P144_B3', 1, (SELECT id FROM book_types WHERE type='T2_P144_type' ORDER BY id DESC LIMIT 1)),
('T2_P144_B4', 1, (SELECT id FROM book_types WHERE type='T2_P144_type' ORDER BY id DESC LIMIT 1));

-- один клиент достаточно
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
SELECT 'P', 'T2_P144_Client', NULL, '1441', '144111'
WHERE NOT EXISTS (SELECT 1 FROM clients WHERE last_name='T2_P144_Client');

-- helper: вставим выдачи (даты не важны)
-- B1: 5 раз
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T2_P144_B1' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE last_name='T2_P144_Client' ORDER BY id DESC LIMIT 1),
       CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE
FROM generate_series(1,5);

-- B2: 4 раза
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T2_P144_B2' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE last_name='T2_P144_Client' ORDER BY id DESC LIMIT 1),
       CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE
FROM generate_series(1,4);

-- B3: 3 раза
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT (SELECT id FROM books WHERE name='T2_P144_B3' ORDER BY id DESC LIMIT 1),
       (SELECT id FROM clients WHERE last_name='T2_P144_Client' ORDER BY id DESC LIMIT 1),
       CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE
FROM generate_series(1,3);

-- B4: 1 раз
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
 (SELECT id FROM books WHERE name='T2_P144_B4' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_P144_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE
);

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT b.name, COUNT(*) AS taken_count
FROM journal j
JOIN books b ON b.id = j.book_id
WHERE b.name LIKE 'T2_P144_%'
GROUP BY b.name
ORDER BY taken_count DESC, b.name
LIMIT 3;
```

**Что ожидаем:** 3 строки (в порядке):
1) `T2_P144_B1` → 5  
2) `T2_P144_B2` → 4  
3) `T2_P144_B3` → 3  

---

# 2) ВСТАВКА ДАННЫХ (INSERT)

## 2.1 Однотабличная вставка
### 2.1.1 Добавить нового клиента

**SETUP (чтобы многоразово)**
```sql
DELETE FROM clients
WHERE last_name='T2_I21_Client'
  AND passpot_seria='2222'
  AND passport_number='222222';
```

**EXECUTE**
```sql
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('New', 'T2_I21_Client', NULL, '2222', '222222')
RETURNING id, first_name, last_name;
```

**TEST**
```sql
SELECT id, first_name, last_name
FROM clients
WHERE last_name='T2_I21_Client'
ORDER BY id DESC
LIMIT 1;
```

**Что ожидаем:** 1 строка `T2_I21_Client`.

---

## 2.2 Многотабличная вставка в рамках транзакции

### 2.2.1 Добавить в транзакции клиента, книгу и запись в journal о выдаче книги этому клиенту

**SETUP (чистим)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name='T2_I221_Book')
   OR client_id IN (SELECT id FROM clients WHERE last_name='T2_I221_Client');

DELETE FROM books WHERE name='T2_I221_Book';
DELETE FROM clients WHERE last_name='T2_I221_Client';
DELETE FROM book_types WHERE type='T2_I221_type';

COMMIT;
```

**EXECUTE (одним блоком)**
```sql
BEGIN;

INSERT INTO book_types(type, fine, day_count)
VALUES ('T2_I221_type', 10, 10);

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('Tran', 'T2_I221_Client', NULL, '2211', '221111');

INSERT INTO books(name, cnt, type_id)
VALUES ('T2_I221_Book', 1, (SELECT id FROM book_types WHERE type='T2_I221_type' ORDER BY id DESC LIMIT 1));

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_I221_Book' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_I221_Client' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE,
  CURRENT_DATE + (SELECT day_count FROM book_types WHERE type='T2_I221_type' ORDER BY id DESC LIMIT 1),
  NULL
)
RETURNING id;

COMMIT;
```

**TEST**
```sql
SELECT
  (SELECT COUNT(*) FROM clients WHERE last_name='T2_I221_Client') AS clients_cnt,
  (SELECT COUNT(*) FROM books   WHERE name='T2_I221_Book')       AS books_cnt,
  (SELECT COUNT(*)
   FROM journal j
   JOIN books b ON b.id=j.book_id
   JOIN clients c ON c.id=j.client_id
   WHERE b.name='T2_I221_Book' AND c.last_name='T2_I221_Client' AND j.date_ret IS NULL) AS journal_cnt;
```

**Что ожидаем:** `clients_cnt=1`, `books_cnt=1`, `journal_cnt=1`.

---

### 2.2.2 Добавить запись в journal, если книг у клиента больше 10 — транзакцию откатить

**SETUP (создаём клиента с 11 книгами на руках)**
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name='T2_I222_Client')
   OR book_id IN (SELECT id FROM books WHERE name LIKE 'T2_I222_B%');

DELETE FROM books WHERE name LIKE 'T2_I222_B%';
DELETE FROM clients WHERE last_name='T2_I222_Client';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_I222_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_I222_type');

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('Limit','T2_I222_Client',NULL,'2223','222333');

-- 11 книг + 11 записей journal (на руках)
INSERT INTO books(name, cnt, type_id)
SELECT 'T2_I222_B' || gs::text, 1, (SELECT id FROM book_types WHERE type='T2_I222_type' ORDER BY id DESC LIMIT 1)
FROM generate_series(1,11) gs;

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
SELECT
  b.id,
  (SELECT id FROM clients WHERE last_name='T2_I222_Client' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE,
  CURRENT_DATE + 1,
  NULL
FROM books b
WHERE b.name LIKE 'T2_I222_B%';

COMMIT;
```

**EXECUTE (должен откатиться и НЕ добавить 12-ю книгу)**
```sql
BEGIN;

DO $$
DECLARE
  v_client_id INT;
  v_onhand    INT;
BEGIN
  SELECT id INTO v_client_id
  FROM clients
  WHERE last_name='T2_I222_Client'
  ORDER BY id DESC
  LIMIT 1;

  SELECT COUNT(*) INTO v_onhand
  FROM journal
  WHERE client_id = v_client_id
    AND date_ret IS NULL;

  IF v_onhand > 10 THEN
    RAISE EXCEPTION 'Too many books on hand: %', v_onhand;
  END IF;

  -- если бы можно было, тут бы вставили новую выдачу
  INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
  VALUES (
    (SELECT id FROM books WHERE name='T2_I222_B1' ORDER BY id DESC LIMIT 1),
    v_client_id,
    CURRENT_DATE,
    CURRENT_DATE + 1,
    NULL
  );
END $$;

COMMIT;
```
```sql
ROLLBACK;
```


**TEST (после ошибки транзакция должна быть откатана клиентом/pgAdmin автоматически; проверяем, что осталось 11)**
```sql
SELECT COUNT(*) AS onhand_after
FROM journal
WHERE client_id = (SELECT id FROM clients WHERE last_name='T2_I222_Client' ORDER BY id DESC LIMIT 1)
  AND date_ret IS NULL;
```

**Что ожидаем:** `onhand_after = 11` (новая запись не добавилась).

> Если pgAdmin не откатил автоматически после EXCEPTION — нажми `ROLLBACK;` (или перезапусти блок как один).

---

# 3) УДАЛЕНИЕ ДАННЫХ (DELETE)

## 3.1 Удалить книги, не имеющие ссылок из записей в журнале

**SETUP (2 книги: одна “осиротевшая”, одна имеет ссылку)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_D31_%')
   OR client_id IN (SELECT id FROM clients WHERE last_name='T2_D31_Client');

DELETE FROM books WHERE name LIKE 'T2_D31_%';
DELETE FROM clients WHERE last_name='T2_D31_Client';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_D31_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_D31_type');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_D31_Orphan', 1, (SELECT id FROM book_types WHERE type='T2_D31_type' ORDER BY id DESC LIMIT 1)),
('T2_D31_Linked', 1, (SELECT id FROM book_types WHERE type='T2_D31_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('C','T2_D31_Client',NULL,'3333','333333');

-- link for Linked
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_D31_Linked' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_D31_Client' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE,
  CURRENT_DATE + 1,
  CURRENT_DATE
);

COMMIT;
```

**EXECUTE (решение + сколько удалилось)**
```sql
WITH del AS (
  DELETE FROM books b
  WHERE b.name LIKE 'T2_D31_%'
    AND NOT EXISTS (SELECT 1 FROM journal j WHERE j.book_id = b.id)
  RETURNING b.name
)
SELECT COUNT(*) AS deleted_books
FROM del;
```

**TEST**
```sql
SELECT name
FROM books
WHERE name LIKE 'T2_D31_%'
ORDER BY name;
```

**Что ожидаем:**  
- `deleted_books = 1` (удалится `T2_D31_Orphan`)  
- в TEST останется только `T2_D31_Linked`

---

## 3.2 Удаление в рамках транзакции

### 3.2.1 Удалить в транзакции книгу и записи о её выдаче (COMMIT)

**SETUP (книга + 2 записи journal)**
```sql
BEGIN;

-- чистим прошлые тесты
DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name='T2_D321_Book');

DELETE FROM books
WHERE name='T2_D321_Book';

-- тип (если нет — создаём)
INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_D321_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_D321_type');

-- книга
INSERT INTO books(name, cnt, type_id)
VALUES (
  'T2_D321_Book',
  1,
  (SELECT id FROM book_types WHERE type='T2_D321_type' ORDER BY id DESC LIMIT 1)
);

-- клиент (если нет — создаём)
INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
SELECT 'D','T2_D321_Client',NULL,'3211','321111'
WHERE NOT EXISTS (SELECT 1 FROM clients WHERE last_name='T2_D321_Client');

-- 2 записи журнала с УНИКАЛЬНЫМИ датами (чтобы TEST не зависел от books после удаления)
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
(
  (SELECT id FROM books WHERE name='T2_D321_Book' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_D321_Client' ORDER BY id DESC LIMIT 1),
  DATE '2099-01-01', DATE '2099-01-02', DATE '2099-01-02'
),
(
  (SELECT id FROM books WHERE name='T2_D321_Book' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_D321_Client' ORDER BY id DESC LIMIT 1),
  DATE '2099-01-03', DATE '2099-01-04', DATE '2099-01-04'
);

COMMIT;
```

**EXECUTE (одним блоком)**
```sql
BEGIN;

WITH target AS (
  SELECT id
  FROM books
  WHERE name='T2_D321_Book'
  ORDER BY id DESC
  LIMIT 1
),
del_j AS (
  -- удаляем все выдачи этой книги
  DELETE FROM journal
  WHERE book_id IN (SELECT id FROM target)
  RETURNING id
),
del_b AS (
  -- удаляем саму книгу
  DELETE FROM books
  WHERE id IN (SELECT id FROM target)
  RETURNING id
)
SELECT
  (SELECT COUNT(*) FROM del_b) AS books_deleted,
  (SELECT COUNT(*) FROM del_j) AS journal_deleted;

COMMIT;
```

**TEST**
```sql
SELECT COUNT(*) AS book_left
FROM books
WHERE name='T2_D321_Book';
```

```sql
SELECT COUNT(*) AS journal_left
FROM journal
WHERE date_beg IN (DATE '2099-01-01', DATE '2099-01-03');
```

**Что ожидаем:** `book_left` = 0, `journal_left` = 0


---

### 3.2.2 То же, но транзакцию откатить (ROLLBACK)

**SETUP (снова книга + 2 journal, чтобы откат было видно)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name='T2_D322_Book');

DELETE FROM books
WHERE name='T2_D322_Book';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_D322_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_D322_type');

INSERT INTO books(name, cnt, type_id)
VALUES ('T2_D322_Book', 1, (SELECT id FROM book_types WHERE type='T2_D322_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
SELECT 'E','T2_D322_Client',NULL,'3221','322111'
WHERE NOT EXISTS (SELECT 1 FROM clients WHERE last_name='T2_D322_Client');

-- 2 записи journal с УНИКАЛЬНЫМИ датами (для надёжного TEST)
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
(
  (SELECT id FROM books WHERE name='T2_D322_Book' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_D322_Client' ORDER BY id DESC LIMIT 1),
  DATE '2099-02-01', DATE '2099-02-02', DATE '2099-02-02'
),
(
  (SELECT id FROM books WHERE name='T2_D322_Book' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_D322_Client' ORDER BY id DESC LIMIT 1),
  DATE '2099-02-03', DATE '2099-02-04', DATE '2099-02-04'
);

COMMIT;
```

**EXECUTE**
```sql
BEGIN;

WITH target AS (
  SELECT id
  FROM books
  WHERE name='T2_D322_Book'
  ORDER BY id DESC
  LIMIT 1
),
del_j AS (
  DELETE FROM journal
  WHERE book_id IN (SELECT id FROM target)
  RETURNING id
),
del_b AS (
  DELETE FROM books
  WHERE id IN (SELECT id FROM target)
  RETURNING id
)
SELECT
  (SELECT COUNT(*) FROM del_b) AS books_deleted,
  (SELECT COUNT(*) FROM del_j) AS journal_deleted;

ROLLBACK;
```

**TEST**
```sql
SELECT COUNT(*) AS book_left
FROM books
WHERE name='T2_D322_Book';
```

```sql
SELECT COUNT(*) AS journal_left
FROM journal
WHERE date_beg IN (DATE '2099-02-01', DATE '2099-02-03');
```

**Что ожидаем:** `book_left=1`, `journal_left=2` (откат сработал).

---

# 4) МОДИФИКАЦИЯ ДАННЫХ (UPDATE)

## 4.1 Модификация по фильтру
### 4.1.1 Заменить уже выданную заданному клиенту книгу на другую

**SETUP (клиент + 2 книги + 1 выдача первой книги)**
```sql
BEGIN;

DELETE FROM journal
WHERE client_id IN (SELECT id FROM clients WHERE last_name='T2_U41_Client')
   OR book_id IN (SELECT id FROM books WHERE name LIKE 'T2_U41_%');

DELETE FROM books WHERE name LIKE 'T2_U41_%';
DELETE FROM clients WHERE last_name='T2_U41_Client';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_U41_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_U41_type');

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
VALUES ('U','T2_U41_Client',NULL,'4141','414111');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_U41_OldBook', 1, (SELECT id FROM book_types WHERE type='T2_U41_type' ORDER BY id DESC LIMIT 1)),
('T2_U41_NewBook', 1, (SELECT id FROM book_types WHERE type='T2_U41_type' ORDER BY id DESC LIMIT 1));

-- выдача OldBook
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret)
VALUES (
  (SELECT id FROM books WHERE name='T2_U41_OldBook' ORDER BY id DESC LIMIT 1),
  (SELECT id FROM clients WHERE last_name='T2_U41_Client' ORDER BY id DESC LIMIT 1),
  CURRENT_DATE,
  CURRENT_DATE + 1,
  NULL
);

COMMIT;
```

**EXECUTE (решение)**
```sql
UPDATE journal
SET book_id = (SELECT id FROM books WHERE name='T2_U41_NewBook' ORDER BY id DESC LIMIT 1)
WHERE client_id = (SELECT id FROM clients WHERE last_name='T2_U41_Client' ORDER BY id DESC LIMIT 1)
  AND date_ret IS NULL
RETURNING id, book_id;
```

**TEST**
```sql
SELECT b.name
FROM journal j
JOIN books b ON b.id=j.book_id
WHERE j.client_id = (SELECT id FROM clients WHERE last_name='T2_U41_Client' ORDER BY id DESC LIMIT 1)
  AND j.date_ret IS NULL;
```

**Что ожидаем:** в TEST вернётся `T2_U41_NewBook`.

---

## 4.2 Модификация в рамках транзакции

### 4.2.1 В транзакции поменять заданную книгу во всех записях журнала на другую и удалить её (COMMIT)

**SETUP (старая книга встречается в 2 записях journal)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_U421_%');

DELETE FROM books WHERE name LIKE 'T2_U421_%';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_U421_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_U421_type');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_U421_Old', 1, (SELECT id FROM book_types WHERE type='T2_U421_type' ORDER BY id DESC LIMIT 1)),
('T2_U421_New', 1, (SELECT id FROM book_types WHERE type='T2_U421_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
SELECT 'M','T2_U421_Client',NULL,'4211','421111'
WHERE NOT EXISTS (SELECT 1 FROM clients WHERE last_name='T2_U421_Client');

-- 2 записи с Old
INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T2_U421_Old' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_U421_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE),
((SELECT id FROM books WHERE name='T2_U421_Old' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_U421_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE);

COMMIT;
```

**EXECUTE**
```sql
BEGIN;

WITH old AS (
  SELECT id FROM books WHERE name='T2_U421_Old' ORDER BY id DESC LIMIT 1
),
new AS (
  SELECT id FROM books WHERE name='T2_U421_New' ORDER BY id DESC LIMIT 1
),
upd AS (
  UPDATE journal
  SET book_id = (SELECT id FROM new)
  WHERE book_id = (SELECT id FROM old)
  RETURNING id
),
del AS (
  DELETE FROM books
  WHERE id = (SELECT id FROM old)
  RETURNING id
)
SELECT
  (SELECT COUNT(*) FROM upd) AS journal_updated,
  (SELECT COUNT(*) FROM del) AS books_deleted;

COMMIT;
```

**TEST**
```sql
SELECT
  (SELECT COUNT(*) FROM journal j
   JOIN books b ON b.id=j.book_id
   WHERE b.name='T2_U421_New') AS links_to_new,

  (SELECT COUNT(*) FROM books WHERE name='T2_U421_Old') AS old_book_left,

  -- чтобы получить journal_updated=2:
  (SELECT COUNT(*) FROM journal j
   WHERE j.book_id = (SELECT id FROM books WHERE name='T2_U421_New' ORDER BY id DESC LIMIT 1)
  ) AS journal_updated_fact,

  -- чтобы получить books_deleted=1:
  (CASE WHEN (SELECT COUNT(*) FROM books WHERE name='T2_U421_Old') = 0 THEN 1 ELSE 0 END) AS books_deleted_fact;
```

**Что ожидаем:** `journal_updated=2`, `books_deleted=1`, `old_book_left=0`, `links_to_new=2`.

---

### 4.2.2 То же, но транзакцию откатить (ROLLBACK)

**SETUP (аналогично: 2 записи на старую книгу)**
```sql
BEGIN;

DELETE FROM journal
WHERE book_id IN (SELECT id FROM books WHERE name LIKE 'T2_U422_%');

DELETE FROM books WHERE name LIKE 'T2_U422_%';

INSERT INTO book_types(type, fine, day_count)
SELECT 'T2_U422_type', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM book_types WHERE type='T2_U422_type');

INSERT INTO books(name, cnt, type_id) VALUES
('T2_U422_Old', 1, (SELECT id FROM book_types WHERE type='T2_U422_type' ORDER BY id DESC LIMIT 1)),
('T2_U422_New', 1, (SELECT id FROM book_types WHERE type='T2_U422_type' ORDER BY id DESC LIMIT 1));

INSERT INTO clients(first_name, last_name, father_name, passpot_seria, passport_number)
SELECT 'N','T2_U422_Client',NULL,'4221','422111'
WHERE NOT EXISTS (SELECT 1 FROM clients WHERE last_name='T2_U422_Client');

INSERT INTO journal(book_id, client_id, date_beg, date_end, date_ret) VALUES
((SELECT id FROM books WHERE name='T2_U422_Old' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_U422_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE),
((SELECT id FROM books WHERE name='T2_U422_Old' ORDER BY id DESC LIMIT 1),
 (SELECT id FROM clients WHERE last_name='T2_U422_Client' ORDER BY id DESC LIMIT 1),
 CURRENT_DATE, CURRENT_DATE+1, CURRENT_DATE);

COMMIT;
```

**EXECUTE**
```sql
BEGIN;

WITH old AS (
  SELECT id FROM books WHERE name='T2_U422_Old' ORDER BY id DESC LIMIT 1
),
new AS (
  SELECT id FROM books WHERE name='T2_U422_New' ORDER BY id DESC LIMIT 1
),
upd AS (
  UPDATE journal
  SET book_id = (SELECT id FROM new)
  WHERE book_id = (SELECT id FROM old)
  RETURNING id
),
del AS (
  DELETE FROM books
  WHERE id = (SELECT id FROM old)
  RETURNING id
)
SELECT
  (SELECT COUNT(*) FROM upd) AS journal_updated,
  (SELECT COUNT(*) FROM del) AS books_deleted;

ROLLBACK;
```

**TEST**
```sql
SELECT
  (SELECT COUNT(*) FROM books WHERE name='T2_U422_Old') AS old_book_left,
  (SELECT COUNT(*)
   FROM journal j
   JOIN books b ON b.id=j.book_id
   WHERE b.name='T2_U422_Old') AS links_to_old;
```

**Что ожидаем:** `old_book_left=1`, `links_to_old=2`.

---

# 5) Теория (кратко)

## 5.1 Что такое DML в PostgreSQL
DML (Data Manipulation Language) — язык манипуляции данными: **SELECT, INSERT, UPDATE, DELETE**.

## 5.2 DELETE vs TRUNCATE
- `DELETE` удаляет строки (можно с `WHERE`), построчно, триггеры могут срабатывать.
- `TRUNCATE` быстро очищает таблицу целиком (без `WHERE`), часто требует `CASCADE` при FK.

## 5.3 JOIN (разница)
- `INNER JOIN` — только совпавшие строки.
- `LEFT JOIN` — все слева + совпадения справа.
- `RIGHT JOIN` — все справа + совпадения слева.
- `FULL OUTER JOIN` — все строки обеих таблиц (несовпавшие заполняются NULL).

---

# 6) Мини-порядок сдачи (контрольные цифры)
1) 1.1.1 → вернётся ровно 1 строка с `date_ret=2025-12-31`  
2) 1.1.2 → `no_stock=1`  
3) 1.2.1 → только `T2_Q121_U_onhand`  
4) 1.3.1 → увидишь 3 строки (Issued+Issued, Client_Never, Book_Never)  
5) 1.4.1 → `on_hand=2`  
6) 1.4.2 → штраф = `70`  
7) 1.4.3 → `max_fine=100`  
8) 1.4.4 → TOP3: B1=5, B2=4, B3=3  
9) 2.2.2 → после ошибки `onhand_after=11`  
10) 3.2.2 / 4.2.2 → rollback сохраняет данные (проверки в TEST)
