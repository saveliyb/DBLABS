# Лабораторная работа №2 — SQL-DML (PostgreSQL)
## Вариант: «Автоматизация работы магазина» — демонстрационный MD (многоразово)

---

## 0) Быстрый чек: таблицы существуют
```sql
SELECT
  to_regclass('public.warehouses')    AS warehouses,
  to_regclass('public.sales')         AS sales,
  to_regclass('public.charges')       AS charges,
  to_regclass('public.expense_items') AS expense_items;
```
**Ожидаем:** везде не `NULL`.

---

# 1) ВЫБОРКА ДАННЫХ (SELECT)

## 1.1 Однотабличная выборка

### 1.1.1 Вычислить общее количество проданных товаров и сумму за всё время работы магазина

> “Сумма” = общая выручка = `SUM(sales.quantity * sales.amount)`.

**SETUP (создаём тестовые товары + продажи с крайними значениями)**
```sql
BEGIN;

-- чистим тестовые продажи/товары
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'T2_Q11_%');

DELETE FROM warehouses
WHERE name LIKE 'T2_Q11_%';

-- два товара на складе (quantity — остаток, amount — цена за штуку)
INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_Q11_Good_A', 999999,  1.00),   -- огромный остаток, минимальная цена
('T2_Q11_Good_B',      1, 99.99);   -- маленький остаток, большая цена

-- три продажи (unit price берём из sales.amount)
INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(1,      1.00,   CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q11_Good_A' ORDER BY id DESC LIMIT 1)),
(1000,   1.00,   CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q11_Good_A' ORDER BY id DESC LIMIT 1)),
(2,     99.99,   CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q11_Good_B' ORDER BY id DESC LIMIT 1));

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  COALESCE(SUM(quantity), 0)                    AS total_qty_sold,
  COALESCE(SUM(quantity * amount), 0)           AS total_revenue
FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'T2_Q11_%');
```

**TEST (показываем конкретные строки, которые суммировались)**
```sql
SELECT s.id, w.name, s.quantity, s.amount, (s.quantity * s.amount) AS line_revenue, s.sale_date
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
WHERE w.name LIKE 'T2_Q11_%'
ORDER BY s.id;
```

**Что ожидаем:**
- `total_qty_sold = 1 + 1000 + 2 = 1003`
- `total_revenue  = 1*1.00 + 1000*1.00 + 2*99.99 = 1.00 + 1000.00 + 199.98 = 1200.98`

---

### 1.1.2 Вывести все расходы за последний месяц

**SETUP (1 расход в пределах месяца и 1 расход старше месяца)**
```sql
BEGIN;

ALTER TABLE charges DISABLE TRIGGER USER;

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'T2_Q12_%');

DELETE FROM expense_items
WHERE name LIKE 'T2_Q12_%';

INSERT INTO expense_items(name) VALUES
('T2_Q12_Item_InMonth'),
('T2_Q12_Item_Old');

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00,  CURRENT_DATE - INTERVAL '10 days', (SELECT id FROM expense_items WHERE name='T2_Q12_Item_InMonth' ORDER BY id DESC LIMIT 1)),
(99.99,  CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM expense_items WHERE name='T2_Q12_Item_Old'     ORDER BY id DESC LIMIT 1));

ALTER TABLE charges ENABLE TRIGGER USER;

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  c.id,
  c.amount,
  c.charge_date,
  ei.name AS expense_item
FROM charges c
JOIN expense_items ei ON ei.id = c.expense_item_id
WHERE
  ei.name LIKE 'T2_Q12_%'
  AND c.charge_date >= (CURRENT_DATE - INTERVAL '1 month')
ORDER BY c.charge_date DESC, c.id DESC;
```

**Что ожидаем:** вернётся **только** строка `T2_Q12_Item_InMonth` с `amount=10.00`.  
Строка `99.99` (40 дней назад) **не должна попасть**.

---

## 1.2 Соединение таблиц (JOIN)

### 1.2.1 Вывести все товары, которые сейчас есть на складе и по которым за последний месяц были продажи

**SETUP (3 товара: 1 подходит, 2 не подходят по разным причинам)**
```sql
BEGIN;

DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'T2_Q121_%');

DELETE FROM warehouses
WHERE name LIKE 'T2_Q121_%';

-- 1) Подходит: quantity > 0 и продажа в последнем месяце
INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_Q121_Good_OK',  5, 10.00);

-- 2) Не подходит: продажа есть, но quantity=0
INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_Q121_Good_NoStock',  0, 10.00);

-- 3) Не подходит: quantity>0, но продажа 40 дней назад
INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_Q121_Good_OldSale',  5, 10.00);

-- продажи
INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(1, 10.00, CURRENT_DATE - INTERVAL '10 days', (SELECT id FROM warehouses WHERE name='T2_Q121_Good_OK'       ORDER BY id DESC LIMIT 1)),
(1, 10.00, CURRENT_DATE - INTERVAL '10 days', (SELECT id FROM warehouses WHERE name='T2_Q121_Good_NoStock'  ORDER BY id DESC LIMIT 1)),
(1, 10.00, CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM warehouses WHERE name='T2_Q121_Good_OldSale'  ORDER BY id DESC LIMIT 1));

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  w.name,
  w.quantity AS stock_quantity,
  MAX(s.sale_date) AS last_sale_date_in_period
FROM warehouses w
JOIN sales s ON s.warehouse_id = w.id
WHERE
  w.name LIKE 'T2_Q121_%'
  AND w.quantity > 0
  AND s.sale_date >= (CURRENT_DATE - INTERVAL '1 month')
GROUP BY w.name, w.quantity
ORDER BY w.name;
```

**Что ожидаем:** **ровно 1 строка**: `T2_Q121_Good_OK`.  
`T2_Q121_Good_NoStock` отсекается по `w.quantity > 0`.  
`T2_Q121_Good_OldSale` отсекается по дате.

---

### 1.2.2 Вывести стоимость каждой статьи расхода за последний год, упорядочив по убыванию

**SETUP (2 статьи: одна с расходами в год, одна без; + расход старше года)**
```sql
BEGIN;

ALTER TABLE charges DISABLE TRIGGER USER;

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'T2_Q122_%');

DELETE FROM expense_items
WHERE name LIKE 'T2_Q122_%';

INSERT INTO expense_items(name) VALUES
('T2_Q122_Item_WithYearCharges'),
('T2_Q122_Item_Zero');

-- В пределах года (200 дней назад) + старше года (400 дней назад)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(300.00, CURRENT_DATE - INTERVAL '200 days', (SELECT id FROM expense_items WHERE name='T2_Q122_Item_WithYearCharges' ORDER BY id DESC LIMIT 1)),
(700.00, CURRENT_DATE - INTERVAL '400 days', (SELECT id FROM expense_items WHERE name='T2_Q122_Item_WithYearCharges' ORDER BY id DESC LIMIT 1));

ALTER TABLE charges ENABLE TRIGGER USER;

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  ei.name,
  COALESCE(SUM(c.amount), 0) AS total_cost_last_year
FROM expense_items ei
LEFT JOIN charges c
  ON c.expense_item_id = ei.id
 AND c.charge_date >= (CURRENT_DATE - INTERVAL '1 year')
WHERE ei.name LIKE 'T2_Q122_%'
GROUP BY ei.name
ORDER BY total_cost_last_year DESC, ei.name;
```

**Что ожидаем:**
1) `T2_Q122_Item_WithYearCharges` → **300.00** (700.00 старше года не учитывается)  
2) `T2_Q122_Item_Zero` → **0**

---

## 1.3 Для реализации проекта

### 1.3.1 Вычислить прибыль магазина за последний месяц

> Прибыль = **выручка за месяц − расходы за месяц**.  
> Выручка = `SUM(sales.quantity * sales.amount)`.

**SETUP (за месяц: выручка 500, расходы 120; вне месяца есть лишние строки)**
```sql
BEGIN;

-- тестовый товар + продажи
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'T2_Q131_%');

DELETE FROM warehouses
WHERE name LIKE 'T2_Q131_%';

INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_Q131_Good', 100, 50.00);

-- продажи: 2 в месяце (5*50 + 5*50 = 500), 1 вне месяца (не должна учитываться)
INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(5, 50.00, CURRENT_DATE - INTERVAL '5 days',  (SELECT id FROM warehouses WHERE name='T2_Q131_Good' ORDER BY id DESC LIMIT 1)),
(5, 50.00, CURRENT_DATE - INTERVAL '10 days', (SELECT id FROM warehouses WHERE name='T2_Q131_Good' ORDER BY id DESC LIMIT 1)),
(1, 50.00, CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM warehouses WHERE name='T2_Q131_Good' ORDER BY id DESC LIMIT 1));

-- тестовые расходы
ALTER TABLE charges DISABLE TRIGGER USER;

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'T2_Q131_%');
DELETE FROM expense_items
WHERE name LIKE 'T2_Q131_%';

INSERT INTO expense_items(name) VALUES ('T2_Q131_Item');

-- расходы: 2 в месяце (120), 1 вне месяца (не должна учитываться)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(20.00,  CURRENT_DATE - INTERVAL '3 days',  (SELECT id FROM expense_items WHERE name='T2_Q131_Item' ORDER BY id DESC LIMIT 1)),
(100.00, CURRENT_DATE - INTERVAL '15 days', (SELECT id FROM expense_items WHERE name='T2_Q131_Item' ORDER BY id DESC LIMIT 1)),
(999.00, CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM expense_items WHERE name='T2_Q131_Item' ORDER BY id DESC LIMIT 1));

ALTER TABLE charges ENABLE TRIGGER USER;

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  COALESCE((
    SELECT SUM(quantity * amount)
    FROM sales
    WHERE sale_date >= (CURRENT_DATE - INTERVAL '1 month')
      AND warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'T2_Q131_%')
  ), 0) AS revenue_last_month,
  COALESCE((
    SELECT SUM(amount)
    FROM charges
    WHERE charge_date >= (CURRENT_DATE - INTERVAL '1 month')
      AND expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'T2_Q131_%')
  ), 0) AS costs_last_month,
  COALESCE((
    SELECT SUM(quantity * amount)
    FROM sales
    WHERE sale_date >= (CURRENT_DATE - INTERVAL '1 month')
      AND warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'T2_Q131_%')
  ), 0)
  -
  COALESCE((
    SELECT SUM(amount)
    FROM charges
    WHERE charge_date >= (CURRENT_DATE - INTERVAL '1 month')
      AND expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'T2_Q131_%')
  ), 0) AS profit_last_month;
```

**Что ожидаем:**
- `revenue_last_month = 500.00`
- `costs_last_month   = 120.00`
- `profit_last_month  = 380.00`

---

### 1.3.2 Пять самых доходных товаров за всё время работы магазина

> Доходность товара = суммарная выручка по товару: `SUM(s.quantity * s.amount)`.

**SETUP (6 товаров, чтобы TOP5 было видно)**
```sql
BEGIN;

DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'T2_Q132_%');

DELETE FROM warehouses
WHERE name LIKE 'T2_Q132_%';

-- 6 товаров
INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_Q132_G1', 1, 1.00),
('T2_Q132_G2', 1, 1.00),
('T2_Q132_G3', 1, 1.00),
('T2_Q132_G4', 1, 1.00),
('T2_Q132_G5', 1, 1.00),
('T2_Q132_G6', 1, 1.00);

-- продажи: сделаем выручки (qty * unit) = 600,500,400,300,200,100
INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(1, 600.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q132_G1' ORDER BY id DESC LIMIT 1)),
(1, 500.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q132_G2' ORDER BY id DESC LIMIT 1)),
(1, 400.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q132_G3' ORDER BY id DESC LIMIT 1)),
(1, 300.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q132_G4' ORDER BY id DESC LIMIT 1)),
(1, 200.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q132_G5' ORDER BY id DESC LIMIT 1)),
(1, 100.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_Q132_G6' ORDER BY id DESC LIMIT 1));

COMMIT;
```

**EXECUTE (решение)**
```sql
SELECT
  w.name,
  COALESCE(SUM(s.quantity), 0)                AS total_qty_sold,
  COALESCE(SUM(s.quantity * s.amount), 0)     AS total_revenue
FROM warehouses w
LEFT JOIN sales s ON s.warehouse_id = w.id
WHERE w.name LIKE 'T2_Q132_%'
GROUP BY w.name
HAVING COALESCE(SUM(s.quantity * s.amount), 0) > 0
ORDER BY total_revenue DESC, w.name
LIMIT 5;
```

**Что ожидаем:** 5 строк в порядке:
1) `T2_Q132_G1` (600)  
2) `T2_Q132_G2` (500)  
3) `T2_Q132_G3` (400)  
4) `T2_Q132_G4` (300)  
5) `T2_Q132_G5` (200)  
`T2_Q132_G6` (100) не попадёт из‑за `LIMIT 5`.

---

# 2) ВСТАВКА ДАННЫХ (INSERT)

## 2.1 Однотабличная вставка

### 2.1.1 Добавить новую статью расхода

**SETUP**
```sql
BEGIN;

ALTER TABLE charges DISABLE TRIGGER USER;

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name = 'T2_I211_Item');

DELETE FROM expense_items
WHERE name = 'T2_I211_Item';

ALTER TABLE charges ENABLE TRIGGER USER;

COMMIT;
```

**EXECUTE**
```sql
INSERT INTO expense_items(name)
VALUES ('T2_I211_Item')
RETURNING id, name;
```

**TEST**
```sql
SELECT id, name
FROM expense_items
WHERE name = 'T2_I211_Item';
```

**Ожидаем:** 1 строка `T2_I211_Item`.

---

### 2.1.2 Добавить в таблицу расходов расход по статье из п.2.1.1

**SETUP**
```sql
INSERT INTO expense_items(name)
SELECT 'T2_I211_Item'
WHERE NOT EXISTS (SELECT 1 FROM expense_items WHERE name='T2_I211_Item');
```

**EXECUTE**
```sql
BEGIN;

ALTER TABLE charges DISABLE TRIGGER USER;

INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (
  9999.99,                 -- крайнее "большое" значение
  CURRENT_DATE,
  (SELECT id FROM expense_items WHERE name='T2_I211_Item' ORDER BY id DESC LIMIT 1)
)
RETURNING id, amount, charge_date, expense_item_id;

ALTER TABLE charges ENABLE TRIGGER USER;

COMMIT;
```

**TEST**
```sql
SELECT c.id, c.amount, c.charge_date, ei.name
FROM charges c
JOIN expense_items ei ON ei.id = c.expense_item_id
WHERE ei.name='T2_I211_Item'
ORDER BY c.id DESC
LIMIT 3;
```

**Ожидаем:** последняя строка с `amount = 9999.99`.

---

## 2.2 Многотабличная вставка в рамках транзакции
### 2.2.1 Добавить новый товар на склад и добавить продажу. Если продаём больше остатка — откатить.

**SETUP**
```sql
BEGIN;

DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='T2_I221_Good');

DELETE FROM warehouses
WHERE name='T2_I221_Good';

COMMIT;
```

**EXECUTE (успешный случай: продаём ровно весь остаток)**
```sql
BEGIN;

INSERT INTO warehouses(name, quantity, amount)
VALUES ('T2_I221_Good', 10, 50.00);

DO $$
DECLARE
  v_wh_id  INT;
  v_stock  INT;
  v_sell_q INT := 10;
  v_unit   NUMERIC;
BEGIN
  SELECT id, quantity, amount
    INTO v_wh_id, v_stock, v_unit
  FROM warehouses
  WHERE name='T2_I221_Good'
  ORDER BY id DESC
  LIMIT 1
  FOR UPDATE;

  IF v_stock < v_sell_q THEN
    RAISE EXCEPTION 'Not enough stock: have %, want %', v_stock, v_sell_q;
  END IF;

  UPDATE warehouses SET quantity = quantity - v_sell_q WHERE id = v_wh_id;

  INSERT INTO sales(quantity, amount, sale_date, warehouse_id)
  VALUES (v_sell_q, v_unit, CURRENT_DATE, v_wh_id);
END $$;

COMMIT;
```

**TEST**
```sql
SELECT name, quantity AS stock_left
FROM warehouses
WHERE name='T2_I221_Good'
ORDER BY id DESC LIMIT 1;

SELECT s.quantity, s.amount, (s.quantity*s.amount) AS line_revenue, s.sale_date
FROM sales s
JOIN warehouses w ON w.id=s.warehouse_id
WHERE w.name='T2_I221_Good'
ORDER BY s.id DESC LIMIT 1;
```

**Ожидаем:** `stock_left = 0`, продажа `quantity=10`, `amount=50.00`, выручка строки = 500.00.

---

**EXECUTE (крайний случай: продаём больше остатка → ошибка и откат)**
```sql
BEGIN;

-- поставим остаток 1
UPDATE warehouses
SET quantity = 1
WHERE name='T2_I221_Good';

DO $$
DECLARE
  v_wh_id  INT;
  v_stock  INT;
  v_sell_q INT := 2;
  v_unit   NUMERIC;
BEGIN
  SELECT id, quantity, amount
    INTO v_wh_id, v_stock, v_unit
  FROM warehouses
  WHERE name='T2_I221_Good'
  ORDER BY id DESC
  LIMIT 1
  FOR UPDATE;

  IF v_stock < v_sell_q THEN
    RAISE EXCEPTION 'Not enough stock: have %, want %', v_stock, v_sell_q;
  END IF;

  UPDATE warehouses SET quantity = quantity - v_sell_q WHERE id = v_wh_id;
  INSERT INTO sales(quantity, amount, sale_date, warehouse_id)
  VALUES (v_sell_q, v_unit, CURRENT_DATE, v_wh_id);
END $$;

COMMIT;
```

**Ожидаем:** ошибка `Not enough stock...` и откат транзакции.

```sql
ROLLBACK;
```

**TEST после ошибки**
```sql
SELECT name, quantity AS stock_left
FROM warehouses
WHERE name='T2_I221_Good'
ORDER BY id DESC LIMIT 1;

SELECT COUNT(*) AS bad_sales_count
FROM sales s
JOIN warehouses w ON w.id=s.warehouse_id
WHERE w.name='T2_I221_Good'
  AND s.quantity=2
  AND s.sale_date=CURRENT_DATE;
```

**Ожидаем:** `bad_sales_count = 0`, остаток не ушёл в минус.

---

# 3) УДАЛЕНИЕ ДАННЫХ (DELETE)

## 3.1 Удаление статьи расхода и всех расходов по ней (многоразово)
---

## **SETUP (создать статью + 2 расхода, чтобы точно было что удалять)**
```sql
BEGIN;

ALTER TABLE charges DISABLE TRIGGER USER;

-- чистим прошлые тесты
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='T2_D31_Item');

DELETE FROM expense_items
WHERE name='T2_D31_Item';

-- создаём статью
INSERT INTO expense_items(name) VALUES ('T2_D31_Item');

-- создаём 2 расхода (крайние значения)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(1.00,    CURRENT_DATE, (SELECT id FROM expense_items WHERE name='T2_D31_Item' ORDER BY id DESC LIMIT 1)),
(999.99,  CURRENT_DATE, (SELECT id FROM expense_items WHERE name='T2_D31_Item' ORDER BY id DESC LIMIT 1));

ALTER TABLE charges ENABLE TRIGGER USER;

COMMIT;
```

**EXECUTE (решение + сразу показываем, сколько удалилось)**
```sql
BEGIN;

ALTER TABLE charges DISABLE TRIGGER USER;

WITH item AS (
  SELECT id
  FROM expense_items
  WHERE name = 'T2_D31_Item'
),
del_charges AS (
  DELETE FROM charges
  WHERE expense_item_id IN (SELECT id FROM item)
  RETURNING id
),
del_item AS (
  DELETE FROM expense_items
  WHERE id IN (SELECT id FROM item)
  RETURNING id
)
SELECT
  (SELECT COUNT(*) FROM del_item)   AS items_deleted,
  (SELECT COUNT(*) FROM del_charges) AS charges_deleted;

ALTER TABLE charges ENABLE TRIGGER USER;

COMMIT;
```

**TEST (проверка “после” — по факту данных)**
```sql
-- 1) статьи нет
SELECT COUNT(*) AS items_left
FROM expense_items
WHERE name='T2_D31_Item';
```
```sql
-- 2) нет расходов, которые “висят” без статьи
SELECT COUNT(*) AS orphan_charges
FROM charges c
LEFT JOIN expense_items ei ON ei.id = c.expense_item_id
WHERE ei.id IS NULL;
```

**Что ожидаем:**
- из EXECUTE: `items_deleted = 1`, `charges_deleted = 2`
- из TEST: `items_left = 0`
- из TEST: `orphan_charges = 0` (иначе у тебя нарушена ссылочная целостность / FK)

## 3.2 Удаление в рамках транзакции

### 3.2.1 Удалить в рамках транзакции продажу товара (по наименованию) с наименьшим количеством

**SETUP (3 продажи: min quantity = 1)**
```sql
BEGIN;

DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='T2_D321_Good');
DELETE FROM warehouses
WHERE name='T2_D321_Good';

INSERT INTO warehouses(name, quantity, amount)
VALUES ('T2_D321_Good', 10, 10.00);

INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(10, 10.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_D321_Good' ORDER BY id DESC LIMIT 1)),
(1,  10.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_D321_Good' ORDER BY id DESC LIMIT 1)), -- минимальная
(2,  10.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_D321_Good' ORDER BY id DESC LIMIT 1));

COMMIT;
```

**EXECUTE**
```sql
BEGIN;

DELETE FROM sales
WHERE id = (
  SELECT s.id
  FROM sales s
  JOIN warehouses w ON w.id=s.warehouse_id
  WHERE w.name='T2_D321_Good'
  ORDER BY s.quantity ASC, s.id ASC
  LIMIT 1
)
RETURNING id, quantity, amount, sale_date;

COMMIT;
```

**Ожидаем:** `RETURNING` покажет `quantity = 1`.

**TEST (проверяем, что остались quantity 2 и 10)**
```sql
SELECT s.quantity, s.amount
FROM sales s
JOIN warehouses w ON w.id=s.warehouse_id
WHERE w.name='T2_D321_Good'
ORDER BY s.quantity;
```

**Ожидаем:** две строки: quantity = 2 и 10.

---

### 3.2.2 То же, но транзакцию откатить

**SETUP (восстановим 3 продажи)**
```sql
BEGIN;

DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='T2_D322_Good');
DELETE FROM warehouses
WHERE name='T2_D322_Good';

INSERT INTO warehouses(name, quantity, amount)
VALUES ('T2_D322_Good', 10, 10.00);

INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(3, 10.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_D322_Good' ORDER BY id DESC LIMIT 1)),
(1, 10.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_D322_Good' ORDER BY id DESC LIMIT 1)),
(2, 10.00, CURRENT_DATE, (SELECT id FROM warehouses WHERE name='T2_D322_Good' ORDER BY id DESC LIMIT 1));

COMMIT;
```

**EXECUTE**
```sql
BEGIN;

DELETE FROM sales
WHERE id = (
  SELECT s.id
  FROM sales s
  JOIN warehouses w ON w.id=s.warehouse_id
  WHERE w.name='T2_D322_Good'
  ORDER BY s.quantity ASC, s.id ASC
  LIMIT 1
)
RETURNING id, quantity;

ROLLBACK;
```

**TEST**
```sql
SELECT COUNT(*) AS sales_left
FROM sales s
JOIN warehouses w ON w.id=s.warehouse_id
WHERE w.name='T2_D322_Good';
```

**Ожидаем:** `sales_left = 3` (удаление откатилось).

---

# 4) МОДИФИКАЦИЯ ДАННЫХ (UPDATE)

## 4.1 Модификация по фильтру
### 4.1.1 Увеличить цену всех товаров на складе на 10%

> Цена товара — `warehouses.amount`.

**SETUP (2 товара: обычная цена и очень большая цена)**
```sql
BEGIN;

DELETE FROM warehouses WHERE name LIKE 'T2_U41_%';

INSERT INTO warehouses(name, quantity, amount) VALUES
('T2_U41_Good_Normal', 1, 100.00),
('T2_U41_Good_Big',    1, 99999.99);

COMMIT;
```

**EXECUTE**
```sql
UPDATE warehouses
SET amount = amount * 1.10
WHERE name LIKE 'T2_U41_%'
RETURNING name, amount;
```

**TEST**
```sql
SELECT name, amount
FROM warehouses
WHERE name LIKE 'T2_U41_%'
ORDER BY name;
```

**Что ожидаем:**
- `T2_U41_Good_Normal` → 110.00  
- `T2_U41_Good_Big` → 109999.989 (или с округлением по вашему типу `NUMERIC(p,s)`)

---

## 4.2 Модификация в рамках транзакции
### 4.2.1 Увеличить цену последней продажи определенного товара на 5.00 (COMMIT)

> “Цена продажи” — `sales.amount` (unit price).

**SETUP (2 продажи, чтобы была “последняя”)**
```sql
BEGIN;

DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='T2_U421_Good');
DELETE FROM warehouses
WHERE name='T2_U421_Good';

INSERT INTO warehouses(name, quantity, amount)
VALUES ('T2_U421_Good', 10, 10.00);

INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(1, 10.00, CURRENT_DATE - INTERVAL '1 day', (SELECT id FROM warehouses WHERE name='T2_U421_Good' ORDER BY id DESC LIMIT 1)),
(1, 10.00, CURRENT_DATE,                (SELECT id FROM warehouses WHERE name='T2_U421_Good' ORDER BY id DESC LIMIT 1)); -- последняя

COMMIT;
```

**EXECUTE**
```sql
BEGIN;

UPDATE sales
SET amount = amount + 5.00
WHERE id = (
  SELECT s.id
  FROM sales s
  JOIN warehouses w ON w.id=s.warehouse_id
  WHERE w.name='T2_U421_Good'
  ORDER BY s.sale_date DESC, s.id DESC
  LIMIT 1
)
RETURNING id, amount, sale_date;

COMMIT;
```

**TEST**
```sql
SELECT s.amount, s.sale_date
FROM sales s
JOIN warehouses w ON w.id=s.warehouse_id
WHERE w.name='T2_U421_Good'
ORDER BY s.sale_date DESC, s.id DESC
LIMIT 1;
```

**Ожидаем:** у последней продажи `amount = 15.00`.

---

### 4.2.2 То же, но транзакцию откатить (ROLLBACK)

**SETUP (снова последняя продажа amount=10.00)**
```sql
BEGIN;

DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='T2_U422_Good');
DELETE FROM warehouses
WHERE name='T2_U422_Good';

INSERT INTO warehouses(name, quantity, amount)
VALUES ('T2_U422_Good', 10, 10.00);

INSERT INTO sales(quantity, amount, sale_date, warehouse_id) VALUES
(1, 10.00, CURRENT_DATE - INTERVAL '1 day', (SELECT id FROM warehouses WHERE name='T2_U422_Good' ORDER BY id DESC LIMIT 1)),
(1, 10.00, CURRENT_DATE,                (SELECT id FROM warehouses WHERE name='T2_U422_Good' ORDER BY id DESC LIMIT 1));

COMMIT;
```

**EXECUTE**
```sql
BEGIN;

UPDATE sales
SET amount = amount + 5.00
WHERE id = (
  SELECT s.id
  FROM sales s
  JOIN warehouses w ON w.id=s.warehouse_id
  WHERE w.name='T2_U422_Good'
  ORDER BY s.sale_date DESC, s.id DESC
  LIMIT 1
)
RETURNING id, amount;

ROLLBACK;
```

**TEST**
```sql
SELECT s.amount
FROM sales s
JOIN warehouses w ON w.id=s.warehouse_id
WHERE w.name='T2_U422_Good'
ORDER BY s.sale_date DESC, s.id DESC
LIMIT 1;
```

**Ожидаем:** `amount` осталось **10.00** (изменение откатилось).

---

# 5) Теория (коротко)

## 5.1 INNER JOIN vs LEFT/RIGHT/FULL OUTER JOIN
- **INNER JOIN** — только строки, у которых есть пара в обеих таблицах.
- **LEFT OUTER JOIN** — все строки слева + совпадения справа (иначе справа `NULL`).
- **RIGHT OUTER JOIN** — все справа + совпадения слева.
- **FULL OUTER JOIN** — все строки обеих таблиц; где пары нет — `NULL` у другой стороны.

## 5.2 DELETE vs TRUNCATE
- **DELETE** — построчно, можно с `WHERE`, триггеры `DELETE` могут сработать.
- **TRUNCATE** — быстро очищает таблицу целиком (без `WHERE`), есть нюансы с FK/`CASCADE`.

## 5.3 Что такое DML
**DML (Data Manipulation Language)** — операции над данными: `SELECT`, `INSERT`, `UPDATE`, `DELETE`.

---

# 6) Быстрый порядок сдачи (ожидаемые цифры)
1) 1.1.1 → `total_qty_sold=1003`, `total_revenue=1200.98`  
2) 1.1.2 → покажет только расход `10.00`  
3) 1.2.1 → ровно 1 строка `T2_Q121_Good_OK`  
4) 1.2.2 → итоги `300` и `0`  
5) 1.3.1 → прибыль `380`  
6) 1.3.2 → TOP5 `G1..G5`  
7) 3.2.1 → удаляется продажа с `quantity=1`  
8) 3.2.2 → `ROLLBACK`, `sales_left=3`  
9) 4.1 → `amount` (цена) * 1.10  
10) 4.2 → commit: `15.00`, rollback: `10.00`
