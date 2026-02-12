# Лабораторная работа №2 — SQL-DML (PostgreSQL)
## Вариант 8: Автоматизация работы магазина

Файл сделан как **шпаргалка для демонстрации**: у каждого подпункта есть
1) **Setup** (вставки под крайние случаи + очистка только тестовых данных),
2) **Решение** (основной запрос/операция),
3) **Проверка** (что показать преподавателю),
4) **Зачем крайние случаи** (очень кратко).

> Все тестовые данные в этом файле помечены префиксами: `T2_`, `ProfitTest*`, `TopTest_*`, `TxItem_*`.

---

# 0) Быстрый чек: таблицы существуют
```sql
SELECT
  to_regclass('public.warehouses')    AS warehouses,
  to_regclass('public.sales')         AS sales,
  to_regclass('public.charges')       AS charges,
  to_regclass('public.expense_items') AS expense_items;
```

---

# 1) Выборка данных (SELECT)

## 1.1 Общее количество проданных товаров и сумма за всё время
### Setup
Ничего не нужно. Если `sales` пустая — `COALESCE` вернёт 0.

### Решение
```sql
SELECT
    COALESCE(SUM(quantity), 0) AS total_sold_qty,
    COALESCE(SUM(quantity * amount), 0) AS total_revenue
FROM sales;
```

### Зачем крайний случай
Проверка “sales пустая” → без `COALESCE` были бы `NULL`.

---

## 1.2 Все расходы за последний месяц
### Setup (2 крайних случая: расход в месяце и расход старше месяца)
```sql
-- очистка ТОЛЬКО тестовых данных
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name IN ('T2_LastMonth','T2_OldMonth'));

DELETE FROM expense_items
WHERE name IN ('T2_LastMonth','T2_OldMonth');

-- статьи
INSERT INTO expense_items(name) VALUES ('T2_LastMonth'), ('T2_OldMonth');

-- расход в последний месяц (должен попасть)
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (
  111.00,
  CURRENT_DATE,
  (SELECT id FROM expense_items WHERE name='T2_LastMonth' ORDER BY id DESC LIMIT 1)
);

-- расход старше месяца (не должен попасть)
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (
  222.00,
  CURRENT_DATE - INTERVAL '40 days',
  (SELECT id FROM expense_items WHERE name='T2_OldMonth' ORDER BY id DESC LIMIT 1)
);
```

### Решение
```sql
SELECT
    c.id, c.amount, c.charge_date, e.name AS expense_item
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
WHERE c.charge_date >= CURRENT_DATE - INTERVAL '1 month'
ORDER BY c.charge_date DESC, c.id DESC;
```

### Проверка (что показать)
Должна быть видна строка `T2_LastMonth`, и НЕ должно быть `T2_OldMonth`.

### Зачем крайние случаи
Проверяем фильтр “последний месяц”.

---

# 2) Соединение таблиц (JOIN)

## 2.1 Товары на складе, по которым были продажи за последний месяц
### Setup (3 крайних случая)
- `T2_NoSalesItem`: есть на складе, продаж нет → НЕ попадёт  
- `T2_OldSalesItem`: есть на складе, продажа 40 дней назад → НЕ попадёт  
- `T2_OutOfStockItem`: quantity=0, продажа сегодня → НЕ попадёт

```sql
-- чистим детей
DELETE FROM sales
WHERE warehouse_id IN (
  SELECT id FROM warehouses WHERE name IN ('T2_NoSalesItem','T2_OldSalesItem','T2_OutOfStockItem')
);

-- чистим родителей
DELETE FROM warehouses
WHERE name IN ('T2_NoSalesItem','T2_OldSalesItem','T2_OutOfStockItem');

-- создаём товары
INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_NoSalesItem',     10,  9.99),
('T2_OldSalesItem',    10, 19.99),
('T2_OutOfStockItem',   0, 15.00);

-- старая продажа (40 дней назад) => не должна попасть в "последний месяц"
INSERT INTO sales(amount, quantity, sale_date, warehouse_id)
VALUES (
  25.00, 1, CURRENT_DATE - INTERVAL '40 days',
  (SELECT id FROM warehouses WHERE name='T2_OldSalesItem' ORDER BY id DESC LIMIT 1)
);

-- свежая продажа, но quantity=0 => не должна попасть
INSERT INTO sales(amount, quantity, sale_date, warehouse_id)
VALUES (
  20.00, 1, CURRENT_DATE,
  (SELECT id FROM warehouses WHERE name='T2_OutOfStockItem' ORDER BY id DESC LIMIT 1)
);
```

### Решение
```sql
SELECT DISTINCT
    w.id, w.name, w.quantity, w.amount
FROM warehouses w
JOIN sales s ON s.warehouse_id = w.id
WHERE w.quantity > 0
  AND s.sale_date >= CURRENT_DATE - INTERVAL '1 month'
ORDER BY w.id;
```

### Проверка
```sql
SELECT id, name, quantity, amount
FROM warehouses
WHERE name IN ('T2_NoSalesItem','T2_OldSalesItem','T2_OutOfStockItem')
ORDER BY id;

SELECT w.name, s.sale_date, s.quantity, s.amount
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
WHERE w.name IN ('T2_OldSalesItem','T2_OutOfStockItem')
ORDER BY s.sale_date DESC;
```

### Зачем крайние случаи
Проверяем 3 условия одновременно: `quantity>0`, “есть продажи”, “продажи за месяц”.

---

## 2.2 Стоимость каждой статьи расхода за последний год, по убыванию стоимости
### Setup (4 крайних случая)
- `T2_NoChargesEver`: расходов нет → сумма 0 (но статья должна появиться)
- `T2_OnlyOldCharges`: расход 400 дней назад → сумма 0 за год
- `T2_BorderYearCharge`: расход ровно 1 год назад → должен ВОЙТИ (>=)
- `T2_ManyCharges`: несколько расходов в пределах года → проверка суммирования

```sql
-- чистим тестовые расходы и статьи
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'T2_%');

DELETE FROM expense_items
WHERE name LIKE 'T2_%';

-- создаём статьи
INSERT INTO expense_items(name) VALUES
('T2_NoChargesEver'),
('T2_OnlyOldCharges'),
('T2_BorderYearCharge'),
('T2_ManyCharges');

-- 400 дней назад (не входит в год)
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (
  999.00,
  CURRENT_DATE - INTERVAL '400 days',
  (SELECT id FROM expense_items WHERE name='T2_OnlyOldCharges' ORDER BY id DESC LIMIT 1)
);

-- ровно 1 год назад (входит в год)
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (
  111.00,
  CURRENT_DATE - INTERVAL '1 year',
  (SELECT id FROM expense_items WHERE name='T2_BorderYearCharge' ORDER BY id DESC LIMIT 1)
);

-- несколько расходов в пределах года (должно суммироваться в 60)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE - INTERVAL '10 days', (SELECT id FROM expense_items WHERE name='T2_ManyCharges' ORDER BY id DESC LIMIT 1)),
(20.00, CURRENT_DATE - INTERVAL '20 days', (SELECT id FROM expense_items WHERE name='T2_ManyCharges' ORDER BY id DESC LIMIT 1)),
(30.00, CURRENT_DATE - INTERVAL '30 days', (SELECT id FROM expense_items WHERE name='T2_ManyCharges' ORDER BY id DESC LIMIT 1));
```

### Решение (LEFT JOIN, потому что “каждой статьи”)
```sql
SELECT
    e.name AS expense_item,
    COALESCE(SUM(c.amount), 0) AS total_cost
FROM expense_items e
LEFT JOIN charges c
    ON c.expense_item_id = e.id
   AND c.charge_date >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY e.name
ORDER BY total_cost DESC;
```

### Проверка
Ожидаемо:
- `T2_ManyCharges` = 60 (самый верх среди тестовых)
- `T2_BorderYearCharge` = 111 (входит)
- `T2_NoChargesEver` = 0, `T2_OnlyOldCharges` = 0

```sql
SELECT e.name, c.amount, c.charge_date
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
WHERE e.name IN ('T2_OnlyOldCharges','T2_BorderYearCharge','T2_ManyCharges')
ORDER BY e.name, c.charge_date DESC;
```

### Зачем крайние случаи
Проверяем “за год”, граничную дату, агрегацию, статьи без расходов и сортировку DESC.

---

# 3) Для реализации проекта

## 3.1 Прибыль магазина за последний месяц
### Setup (крайние случаи: старые записи, граница 1 month, сегодня)
```sql
-- чистим тестовые данные ProfitTest*
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='ProfitTestItem');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='ProfitTestExpense');

DELETE FROM warehouses WHERE name='ProfitTestItem';
DELETE FROM expense_items WHERE name='ProfitTestExpense';

-- создаём товар и статью
INSERT INTO warehouses(name, quantity, amount) VALUES ('ProfitTestItem', 999, 10.00);
INSERT INTO expense_items(name) VALUES ('ProfitTestExpense');

-- старые записи (40 дней) — НЕ должны войти
INSERT INTO sales(amount, quantity, sale_date, warehouse_id)
VALUES (20.00, 2, CURRENT_DATE - INTERVAL '40 days',
        (SELECT id FROM warehouses WHERE name='ProfitTestItem' ORDER BY id DESC LIMIT 1));

INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (500.00, CURRENT_DATE - INTERVAL '40 days',
        (SELECT id FROM expense_items WHERE name='ProfitTestExpense' ORDER BY id DESC LIMIT 1));

-- граница "ровно месяц назад" — ДОЛЖНО войти (>=)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id)
VALUES (20.00, 1, CURRENT_DATE - INTERVAL '1 month',
        (SELECT id FROM warehouses WHERE name='ProfitTestItem' ORDER BY id DESC LIMIT 1));

INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (100.00, CURRENT_DATE - INTERVAL '1 month',
        (SELECT id FROM expense_items WHERE name='ProfitTestExpense' ORDER BY id DESC LIMIT 1));

-- сегодня — ДОЛЖНО войти
INSERT INTO sales(amount, quantity, sale_date, warehouse_id)
VALUES (30.00, 3, CURRENT_DATE,
        (SELECT id FROM warehouses WHERE name='ProfitTestItem' ORDER BY id DESC LIMIT 1));

INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (999.00, CURRENT_DATE,
        (SELECT id FROM expense_items WHERE name='ProfitTestExpense' ORDER BY id DESC LIMIT 1));
```

### Проверка “что попало в последний месяц”
```sql
SELECT 'sales' AS t, s.id, s.sale_date, (s.quantity * s.amount) AS money
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
WHERE w.name='ProfitTestItem'
  AND s.sale_date >= CURRENT_DATE - INTERVAL '1 month'
ORDER BY s.sale_date;

SELECT 'charges' AS t, c.id, c.charge_date, c.amount AS money
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
WHERE e.name='ProfitTestExpense'
  AND c.charge_date >= CURRENT_DATE - INTERVAL '1 month'
ORDER BY c.charge_date;
```

### Решение (прибыль = выручка − расходы)
```sql
WITH income AS (
    SELECT COALESCE(SUM(quantity * amount), 0) AS v
    FROM sales
    WHERE sale_date >= CURRENT_DATE - INTERVAL '1 month'
),
expense AS (
    SELECT COALESCE(SUM(amount), 0) AS v
    FROM charges
    WHERE charge_date >= CURRENT_DATE - INTERVAL '1 month'
)
SELECT income.v - expense.v AS profit_last_month
FROM income, expense;
```

### Зачем крайние случаи
- Старые записи доказывают, что фильтр по месяцу работает.
- Запись на границе “1 month” доказывает корректность `>=`.
- COALESCE защищает от NULL (если продаж/расходов нет).

---

## 3.2 Пять самых доходных товаров за всё время
### Setup (6 товаров, чтобы LIMIT 5 был виден + крайние случаи)
Крайние случаи:
- `TopTest_NoSales` — без продаж (не попадёт в INNER JOIN версии)
- `TopTest_Free` — продажа с amount=0 → revenue=0
- `TopTest_Big` — очень большая выручка → #1
- `TopTest_TieA`/`TopTest_TieB` — одинаковая выручка → проверка tie-breaker
- `TopTest_Mid` — средняя выручка

```sql
-- чистим прошлые TopTest_* данные
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'TopTest_%');

DELETE FROM warehouses
WHERE name LIKE 'TopTest_%';

-- создаём 6 товаров
INSERT INTO warehouses (name, quantity, amount) VALUES
('TopTest_NoSales', 10, 10.00),
('TopTest_Free',    10, 10.00),
('TopTest_Big',     10, 10.00),
('TopTest_TieA',    10, 10.00),
('TopTest_TieB',    10, 10.00),
('TopTest_Mid',     10, 10.00);

-- revenue=0 (amount=0, quantity>0)
INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
VALUES (0.00, 5, CURRENT_DATE,
        (SELECT id FROM warehouses WHERE name='TopTest_Free' ORDER BY id DESC LIMIT 1));

-- huge revenue = 100*100 = 10000
INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
VALUES (100.00, 100, CURRENT_DATE,
        (SELECT id FROM warehouses WHERE name='TopTest_Big' ORDER BY id DESC LIMIT 1));

-- tie revenue = 500
INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
VALUES (10.00, 50, CURRENT_DATE,
        (SELECT id FROM warehouses WHERE name='TopTest_TieA' ORDER BY id DESC LIMIT 1));

INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
VALUES (20.00, 25, CURRENT_DATE,
        (SELECT id FROM warehouses WHERE name='TopTest_TieB' ORDER BY id DESC LIMIT 1));

-- mid revenue = 300
INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
VALUES (10.00, 30, CURRENT_DATE,
        (SELECT id FROM warehouses WHERE name='TopTest_Mid' ORDER BY id DESC LIMIT 1));
```

### Решение
```sql
SELECT
    w.id,
    w.name,
    SUM(s.quantity) AS sold_qty,
    SUM(s.quantity * s.amount) AS revenue
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
GROUP BY w.id, w.name
ORDER BY revenue DESC, w.name ASC
LIMIT 5;
```

### Проверка (показать отдельно только TopTest_*)
```sql
SELECT
    w.name,
    COALESCE(SUM(s.quantity * s.amount), 0) AS revenue
FROM warehouses w
LEFT JOIN sales s ON s.warehouse_id = w.id
WHERE w.name LIKE 'TopTest_%'
GROUP BY w.name
ORDER BY revenue DESC, w.name;
```

### Зачем крайние случаи
Показываем сортировку, LIMIT 5, товар без продаж, нулевую выручку и равенство выручек (tie).

---

# 4) Вставка данных (INSERT)

## 4.1 Однотабличная вставка
### 4.1.1 Добавить новую статью расхода
### 4.1.2 Добавить расход по статье из п.1  fileciteturn6file0

### Setup (чтобы можно было запускать много раз)
```sql
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='Advertising');

DELETE FROM expense_items
WHERE name='Advertising';
```

### Решение
```sql
INSERT INTO expense_items (name)
VALUES ('Advertising');
```

```sql
INSERT INTO charges (amount, charge_date, expense_item_id)
VALUES (
    250.00,
    CURRENT_DATE,
    (SELECT id
     FROM expense_items
     WHERE name = 'Advertising'
     ORDER BY id DESC
     LIMIT 1)
);
```

### Проверка
```sql
SELECT
    c.id,
    e.name AS expense_item,
    c.amount,
    c.charge_date
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
WHERE e.name = 'Advertising'
ORDER BY c.id DESC;
```

### Зачем крайний случай
Запуск “много раз” без накопления мусора (cleanup перед тестом).

---

## 4.2 Многотабличная вставка в рамках транзакции
**Задание:** добавить новый товар на склад и запись о продаже. Если stock < sell — откат. fileciteturn6file0

### Кейс 1: sell > stock (должен быть откат)
```sql
DELETE FROM sales WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TxItem_Fail');
DELETE FROM warehouses WHERE name='TxItem_Fail';

BEGIN;

INSERT INTO warehouses (name, quantity, amount)
VALUES ('TxItem_Fail', 3, 10.00);

DO $$
DECLARE
    v_id bigint;
    v_stock int;
    v_sell int := 5;
BEGIN
    SELECT id, quantity INTO v_id, v_stock
    FROM warehouses
    WHERE name = 'TxItem_Fail'
    ORDER BY id DESC
    LIMIT 1;

    IF v_stock < v_sell THEN
        RAISE EXCEPTION 'Not enough stock: have %, need %', v_stock, v_sell;
    END IF;

    INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
    VALUES (12.00, v_sell, CURRENT_DATE, v_id);
END $$;

COMMIT; -- не выполнится
```

После ошибки:
```sql
ROLLBACK;
```

Проверка (должно быть 0 строк):
```sql
SELECT * FROM warehouses WHERE name='TxItem_Fail';
SELECT * FROM sales WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TxItem_Fail');
```

### Кейс 2: sell = stock (коммит)
```sql
DELETE FROM sales WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TxItem_Equal');
DELETE FROM warehouses WHERE name='TxItem_Equal';

BEGIN;

INSERT INTO warehouses (name, quantity, amount)
VALUES ('TxItem_Equal', 4, 10.00);

DO $$
DECLARE
    v_id bigint;
    v_stock int;
    v_sell int := 4;
BEGIN
    SELECT id, quantity INTO v_id, v_stock
    FROM warehouses
    WHERE name = 'TxItem_Equal'
    ORDER BY id DESC
    LIMIT 1;

    IF v_stock < v_sell THEN
        RAISE EXCEPTION 'Not enough stock: have %, need %', v_stock, v_sell;
    END IF;

    INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
    VALUES (12.00, v_sell, CURRENT_DATE, v_id);
END $$;

COMMIT;
```

Проверка:
```sql
SELECT * FROM warehouses WHERE name='TxItem_Equal';
SELECT s.id, w.name, s.quantity, s.amount, s.sale_date
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
WHERE w.name='TxItem_Equal'
ORDER BY s.id DESC;
```

### Кейс 3: sell < stock (коммит)
```sql
DELETE FROM sales WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TxItem_Ok');
DELETE FROM warehouses WHERE name='TxItem_Ok';

BEGIN;

INSERT INTO warehouses (name, quantity, amount)
VALUES ('TxItem_Ok', 10, 10.00);

DO $$
DECLARE
    v_id bigint;
    v_stock int;
    v_sell int := 3;
BEGIN
    SELECT id, quantity INTO v_id, v_stock
    FROM warehouses
    WHERE name = 'TxItem_Ok'
    ORDER BY id DESC
    LIMIT 1;

    IF v_stock < v_sell THEN
        RAISE EXCEPTION 'Not enough stock: have %, need %', v_stock, v_sell;
    END IF;

    INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
    VALUES (12.00, v_sell, CURRENT_DATE, v_id);
END $$;

COMMIT;
```

### Кейс 4: sell = 0 (ошибка CHECK в sales → откат)
```sql
DELETE FROM sales WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TxItem_Zero');
DELETE FROM warehouses WHERE name='TxItem_Zero';

BEGIN;

INSERT INTO warehouses (name, quantity, amount)
VALUES ('TxItem_Zero', 10, 10.00);

INSERT INTO sales (amount, quantity, sale_date, warehouse_id)
VALUES (
    12.00,
    0, -- нарушает CHECK (quantity > 0)
    CURRENT_DATE,
    (SELECT id FROM warehouses WHERE name='TxItem_Zero' ORDER BY id DESC LIMIT 1)
);

COMMIT; -- не выполнится
```

После ошибки:
```sql
ROLLBACK;
```

Проверка:
```sql
SELECT * FROM warehouses WHERE name='TxItem_Zero';
```

### Зачем крайние случаи
- `sell > stock` — требование задания (rollback).
- `sell = stock` — граница допустимого.
- `sell < stock` — обычный успешный сценарий.
- `sell = 0` — проверка ограничений таблицы (CHECK) и отката транзакции.

---

# 5) Теоретические вопросы (ЛР2)

## 5.1 Что такое DML в PostgreSQL?
DML (Data Manipulation Language) — команды для работы с данными:
`SELECT`, `INSERT`, `UPDATE`, `DELETE`.  
Меняют/читают **содержимое** таблиц (не структуру).

## 5.2 Чем отличаются INNER JOIN и LEFT/RIGHT/FULL OUTER JOIN?
- `INNER JOIN`: только строки, где есть совпадение в обеих таблицах.
- `LEFT JOIN`: все строки слева + совпадения справа (иначе справа NULL).
- `RIGHT JOIN`: все строки справа + совпадения слева.
- `FULL JOIN`: все строки с обеих сторон, где нет пары — NULL с другой стороны.

## 5.3 DELETE vs TRUNCATE
- `DELETE`: можно `WHERE`, построчно, триггеры `DELETE` срабатывают.
- `TRUNCATE`: быстро удаляет все строки без `WHERE`, “массовая” операция.
В PostgreSQL обе команды транзакционные, но поведение и стоимость разные.

---

# 6) Быстрый финальный показ состояния (по желанию)
```sql
SELECT * FROM warehouses ORDER BY id;
SELECT * FROM sales ORDER BY id;
SELECT * FROM expense_items ORDER BY id;
SELECT * FROM charges ORDER BY id;
```
