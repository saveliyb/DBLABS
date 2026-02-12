# Лабораторная работа №3 — VIEW / PROCEDURE / TRIGGER / CURSOR (PostgreSQL)
## Вариант 8 — Автоматизация работы магазина

Формат демонстрации: **SETUP → CREATE → TEST → Что делает блок → Что ожидаем и почему**  
Все тестовые данные имеют префикс: `TEST_L3_`

> Важно: файл рассчитан на многократный запуск. Перед созданием объектов — `DROP ... IF EXISTS`.  
> В тестах используются **только** строки `TEST_L3_%`, чтобы не мешали данные из ЛР1/ЛР2.

---

# 0) Очистка тестовых данных (безопасно)

### Что делает блок (коротко):
Отключаем пользовательские триггеры на `charges/sales` → удаляем только тестовые строки `TEST_L3_%` → включаем триггеры обратно.

```sql
BEGIN;

ALTER TABLE charges DISABLE TRIGGER USER;
ALTER TABLE sales   DISABLE TRIGGER USER;

-- удаляем “детей”
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'TEST_L3_%');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'TEST_L3_%');

-- удаляем “родителей”
DELETE FROM warehouses WHERE name LIKE 'TEST_L3_%';
DELETE FROM expense_items WHERE name LIKE 'TEST_L3_%';

ALTER TABLE charges ENABLE TRIGGER USER;
ALTER TABLE sales   ENABLE TRIGGER USER;

COMMIT;
```

**Ожидаем:** удалятся только строки, где имя начинается с `TEST_L3_`.  
**Почему:** триггеры могут блокировать удаление “старых” тестовых расходов; отключение делает очистку воспроизводимой.

---

# 1) VIEW

## 1.1 VIEW: статьи расходов, где сумма расходов за всё время > 1000

### 1.1.1 SETUP

### Что делает блок (коротко):
Создаём 3 статьи расходов:
- `OverLimit` с суммой **1000.01** (должна попасть в VIEW)
- `ExactlyLimit` с суммой **1000.00** (не должна попасть при `> 1000`)
- `NoCharges` без расходов (не должна попасть из-за `JOIN`)

```sql
-- чистим только этот тест (на всякий случай)
DELETE FROM charges
WHERE expense_item_id IN (
  SELECT id FROM expense_items
  WHERE name IN ('TEST_L3_OverLimit','TEST_L3_ExactlyLimit','TEST_L3_NoCharges')
);

DELETE FROM expense_items
WHERE name IN ('TEST_L3_OverLimit','TEST_L3_ExactlyLimit','TEST_L3_NoCharges');

-- создаём статьи
INSERT INTO expense_items(name) VALUES
('TEST_L3_OverLimit'),
('TEST_L3_ExactlyLimit'),
('TEST_L3_NoCharges');

-- OverLimit = 600 + 400.01 = 1000.01  (должна попасть)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(600.00,  CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_OverLimit' ORDER BY id DESC LIMIT 1)),
(400.01,  CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_OverLimit' ORDER BY id DESC LIMIT 1));

-- ExactlyLimit = 700 + 300 = 1000.00 (НЕ должна попасть)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(700.00,  CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_ExactlyLimit' ORDER BY id DESC LIMIT 1)),
(300.00,  CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_ExactlyLimit' ORDER BY id DESC LIMIT 1));
```

**Ожидаем:** данные вставились; `TEST_L3_NoCharges` существует без строк в `charges`.  
**Почему:** дальше VIEW покажет разницу между `> 1000` и `= 1000`, и поведение `JOIN`.

### 1.1.2 CREATE VIEW

### Что делает блок (коротко):
Создаёт представление, которое агрегирует расходы по статье и оставляет только те, где сумма строго больше 1000.

```sql
DROP VIEW IF EXISTS v_expense_items_over_limit;

CREATE VIEW v_expense_items_over_limit AS
SELECT
  e.id,
  e.name AS expense_item,
  SUM(c.amount) AS total_amount
FROM expense_items e
JOIN charges c ON c.expense_item_id = e.id
GROUP BY e.id, e.name
HAVING SUM(c.amount) > 1000.00
ORDER BY total_amount DESC;
```

**Ожидаем:** `CREATE VIEW`.  
**Почему:** VIEW — сохранённый запрос (данные не создаёт).

### 1.1.3 TEST

### Что делает блок (коротко):
Смотрим результат VIEW только по тестовым строкам.

```sql
SELECT *
FROM v_expense_items_over_limit
WHERE expense_item LIKE 'TEST_L3_%'
ORDER BY total_amount DESC;
```

**Ожидаем:** будет только `TEST_L3_OverLimit` (1000.01).  
**Почему:** `ExactlyLimit` не проходит `> 1000`, а `NoCharges` не имеет строк в `charges` и не попадает из-за `JOIN`.

---

## 1.2 VIEW: количество расходов за последний месяц по статьям

### 1.2.1 SETUP

### Что делает блок (коротко):
Делаем 2 статьи:
- `MonthA`: 2 расхода в пределах месяца + 1 расход 40 дней назад (не должен учитываться)
- `MonthB`: расход ровно `1 month` назад (должен учитываться при `>=`)

```sql
DELETE FROM charges
WHERE expense_item_id IN (
  SELECT id FROM expense_items WHERE name IN ('TEST_L3_MonthA','TEST_L3_MonthB')
);

DELETE FROM expense_items
WHERE name IN ('TEST_L3_MonthA','TEST_L3_MonthB');

INSERT INTO expense_items(name) VALUES ('TEST_L3_MonthA'), ('TEST_L3_MonthB');

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE,                     (SELECT id FROM expense_items WHERE name='TEST_L3_MonthA' ORDER BY id DESC LIMIT 1)),
(20.00, CURRENT_DATE - INTERVAL '10 days',(SELECT id FROM expense_items WHERE name='TEST_L3_MonthA' ORDER BY id DESC LIMIT 1)),
(30.00, CURRENT_DATE - INTERVAL '40 days',(SELECT id FROM expense_items WHERE name='TEST_L3_MonthA' ORDER BY id DESC LIMIT 1));

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(15.00, CURRENT_DATE - INTERVAL '1 month',(SELECT id FROM expense_items WHERE name='TEST_L3_MonthB' ORDER BY id DESC LIMIT 1));
```

**Ожидаем:** у `MonthA` 3 записи, но одна старше месяца; у `MonthB` 1 пограничная запись.  
**Почему:** проверяем границу “последний месяц”.

### 1.2.2 CREATE VIEW

### Что делает блок (коротко):
Создаёт представление, которое считает количество расходов за последний месяц по каждой статье.

```sql
DROP VIEW IF EXISTS v_expense_count_last_month_by_item;

CREATE VIEW v_expense_count_last_month_by_item AS
SELECT
  e.name AS expense_item,
  COUNT(*) AS charges_count_last_month
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
WHERE c.charge_date >= CURRENT_DATE - INTERVAL '1 month'
GROUP BY e.name
ORDER BY charges_count_last_month DESC, expense_item;
```

**Ожидаем:** `CREATE VIEW`.  
**Почему:** фильтрация по дате в WHERE оставляет только последние 1 month.

### 1.2.3 TEST

### Что делает блок (коротко):
Проверяем счётчики по тестовым статьям.

```sql
SELECT *
FROM v_expense_count_last_month_by_item
WHERE expense_item LIKE 'TEST_L3_%'
ORDER BY charges_count_last_month DESC, expense_item;
```

**Ожидаем:** `TEST_L3_MonthA = 2`, `TEST_L3_MonthB = 1`.  
**Почему:** расход “40 days” исключается, “1 month” включается из-за `>=`.

---

# 2) 

## 2.1 PROCEDURE (без параметров): все товары + средняя цена их продаж за всё время

### 2.1.1 SETUP
### Что делает блок
создаём 3 товара: с 2 продажами (avg считается), 2) без продаж (avg = 0), 3) с одной продажей (avg = amount).

```sql
-- очистка
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'TEST_L3_PAVG_%');
DELETE FROM warehouses WHERE name LIKE 'TEST_L3_PAVG_%';

-- товары
INSERT INTO warehouses(name, quantity, amount) VALUES
('TEST_L3_PAVG_WithSales',  10, 10.00),
('TEST_L3_PAVG_NoSales',    10, 10.00),
('TEST_L3_PAVG_OneSale',    10, 10.00);

-- продажи: WithSales (две разные цены => avg=15), OneSale (одна цена => avg=7)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(10.00, 1, CURRENT_DATE - 2, (SELECT id FROM warehouses WHERE name='TEST_L3_PAVG_WithSales' ORDER BY id DESC LIMIT 1)),
(20.00, 1, CURRENT_DATE - 1, (SELECT id FROM warehouses WHERE name='TEST_L3_PAVG_WithSales' ORDER BY id DESC LIMIT 1)),
(7.00,  1, CURRENT_DATE,     (SELECT id FROM warehouses WHERE name='TEST_L3_PAVG_OneSale'   ORDER BY id DESC LIMIT 1));
```

**Ожидаем**: 3 товара созданы, продажи есть у 2 из них.
**Почему**: проверяем “есть продажи / нет продаж / одна продажа”.

### 2.1.2 CREATE

### Что делаем
создаём процедуру, которая выводит (`SELECT`) все товары и среднюю цену продаж по каждому.

```sql
DROP PROCEDURE IF EXISTS p_goods_avg_sale_price_all_time();

CREATE PROCEDURE p_goods_avg_sale_price_all_time()
LANGUAGE plpgsql
AS $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT
      w.id,
      w.name,
      COALESCE(AVG(s.amount), 0) AS avg_sale_price
    FROM warehouses w
    LEFT JOIN sales s ON s.warehouse_id = w.id
    GROUP BY w.id, w.name
    ORDER BY w.id
  LOOP
    RAISE NOTICE 'ID: %, Name: %, Avg price: %',
      r.id, r.name, r.avg_sale_price;
  END LOOP;
END;
$$;
```

### 2.1.3 TEST
### Что делаем: вызываем процедуру.

```sql
CALL p_goods_avg_sale_price_all_time();
```
**Ожидаем увидеть** (по тестовым товарам):

`TEST_L3_PAVG_WithSales` → 15.00

`TEST_L3_PAVG_OneSale` → 7.00

`TEST_L3_PAVG_NoSales` → 0

**Почему**: AVG по `NULL` даёт `NULL`, мы заменяем на `0` через `COALESCE`.

# 2.2 PROCEDURE (2 входных параметра): даты, когда два товара продавались в один день

### 2.2.1 SETUP
### Что делаем
создаём 2 товара:
- 1 общая дата продаж **(должна попасть)**
- 1 дата только у одного товара **(не должна попасть)**
```sql
-- очистка
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'TEST_L3_PAIR_%');
DELETE FROM warehouses WHERE name LIKE 'TEST_L3_PAIR_%';

-- товары
INSERT INTO warehouses(name, quantity, amount) VALUES
('TEST_L3_PAIR_A', 10, 10.00),
('TEST_L3_PAIR_B', 10, 10.00);

-- общая дата (должна попасть)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(10.00, 1, CURRENT_DATE - 2, (SELECT id FROM warehouses WHERE name='TEST_L3_PAIR_A' ORDER BY id DESC LIMIT 1)),
(11.00, 1, CURRENT_DATE - 2, (SELECT id FROM warehouses WHERE name='TEST_L3_PAIR_B' ORDER BY id DESC LIMIT 1));

-- дата только у A (не должна попасть)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(12.00, 1, CURRENT_DATE - 1, (SELECT id FROM warehouses WHERE name='TEST_L3_PAIR_A' ORDER BY id DESC LIMIT 1));
```

### 2.2.2 CREATE
### Что делаем: 
создаём процедуру с параметрами good1, good2, которая выводит даты пересечения.

```sql
DROP PROCEDURE IF EXISTS p_dates_when_two_goods_sold_together(text, text);

CREATE PROCEDURE p_dates_when_two_goods_sold_together(IN good1 text, IN good2 text)
LANGUAGE plpgsql
AS $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT DISTINCT s1.sale_date
    FROM sales s1
    JOIN warehouses w1 ON w1.id = s1.warehouse_id
    WHERE w1.name = good1
      AND EXISTS (
        SELECT 1
        FROM sales s2
        JOIN warehouses w2 ON w2.id = s2.warehouse_id
        WHERE w2.name = good2
          AND s2.sale_date = s1.sale_date
      )
    ORDER BY s1.sale_date
  LOOP
    RAISE NOTICE 'Common sale date for % and %: %', good1, good2, r.sale_date;
  END LOOP;

  -- чтобы было понятно, что процедура отработала даже если пересечений нет:
  IF NOT FOUND THEN
    RAISE NOTICE 'No common sale dates for % and %', good1, good2;
  END IF;
END;
$$;
```

### 2.2.3 TEST
### Что делаем
вызываем на наших тестовых товарах.
```sql
CALL p_dates_when_two_goods_sold_together('TEST_L3_PAIR_A','TEST_L3_PAIR_B');
```
**Ожидаем**: одна дата CURRENT_DATE - 2.
**Почему**: только в этот день оба товара продавались

## 2.3 PROCEDURE с OUT: доход и расход за период (date1..date2)

### 2.3.1 SETUP

### Что делает блок (коротко):
Создаём тестовый товар и тестовую статью расходов, добавляем 1 продажу/расход **внутри** периода и 1 продажу/расход **вне** периода.

```sql
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TEST_L3_PeriodGood');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_PeriodExpense');

DELETE FROM warehouses WHERE name='TEST_L3_PeriodGood';
DELETE FROM expense_items WHERE name='TEST_L3_PeriodExpense';

INSERT INTO warehouses(name, quantity, amount) VALUES ('TEST_L3_PeriodGood', 100, 10.00);
INSERT INTO expense_items(name) VALUES ('TEST_L3_PeriodExpense');

-- В периоде: income = 20*2 = 40
INSERT INTO sales(amount, quantity, sale_date, warehouse_id)
VALUES (20.00, 2, CURRENT_DATE - 5,
       (SELECT id FROM warehouses WHERE name='TEST_L3_PeriodGood' ORDER BY id DESC LIMIT 1));

-- В периоде: expense = 15
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (15.00, CURRENT_DATE - 7,
       (SELECT id FROM expense_items WHERE name='TEST_L3_PeriodExpense' ORDER BY id DESC LIMIT 1));

-- ВНЕ периода (не должно войти)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id)
VALUES (20.00, 2, CURRENT_DATE - 50,
       (SELECT id FROM warehouses WHERE name='TEST_L3_PeriodGood' ORDER BY id DESC LIMIT 1));

INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (15.00, CURRENT_DATE - 70,
       (SELECT id FROM expense_items WHERE name='TEST_L3_PeriodExpense' ORDER BY id DESC LIMIT 1));
```

**Ожидаем:** внутри периода есть ровно 1 продажа и 1 расход.  
**Почему:** это “крайний случай” на фильтрацию по диапазону дат.

### 2.3.2 CREATE PROCEDURE

### Что делает блок (коротко):
Создаёт процедуру, которая считает доход/расход **только по тестовым сущностям** и возвращает через `OUT`.

```sql
DROP PROCEDURE IF EXISTS p_income_expense_for_period(date, date, numeric, numeric);

CREATE PROCEDURE p_income_expense_for_period(
  IN date1 date,
  IN date2 date,
  OUT income_total numeric,
  OUT expense_total numeric
)
LANGUAGE plpgsql
AS $$
BEGIN
  SELECT COALESCE(SUM(s.quantity * s.amount), 0)
    INTO income_total
  FROM sales s
  JOIN warehouses w ON w.id = s.warehouse_id
  WHERE s.sale_date BETWEEN date1 AND date2
    AND w.name = 'TEST_L3_PeriodGood';

  SELECT COALESCE(SUM(c.amount), 0)
    INTO expense_total
  FROM charges c
  JOIN expense_items e ON e.id = c.expense_item_id
  WHERE c.charge_date BETWEEN date1 AND date2
    AND e.name = 'TEST_L3_PeriodExpense';
END;
$$;
```

**Ожидаем:** `CREATE PROCEDURE`.  
**Почему:** `SELECT ... INTO` заполняет `OUT` параметры.

### 2.3.3 TEST

### Что делает блок (коротко):
Вызываем процедуру (2 IN + 2 OUT → в `CALL` 4 аргумента).

```sql
CALL p_income_expense_for_period(CURRENT_DATE - 10, CURRENT_DATE, NULL, NULL);
```

**Ожидаем:** `income_total = 40`, `expense_total = 15`.  
**Почему:** учитываются только тестовые строки и только внутри периода.

---

# 3) TRIGGER

## 3.1 BEFORE INSERT ON charges: запрет amount > 5000

### 3.1.1 CREATE + SETUP

### Что делает блок (коротко):
Удаляем старые объекты → создаём тестовую статью → создаём триггер-функцию → вешаем триггер на `charges`.

```sql
DROP TRIGGER IF EXISTS trg_charges_amount_limit ON charges;
DROP FUNCTION IF EXISTS f_charges_amount_limit();

-- SETUP: статья расходов + очистка старых тестовых charges по ней
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_TrigExpense');

DELETE FROM expense_items WHERE name='TEST_L3_TrigExpense';
INSERT INTO expense_items(name) VALUES ('TEST_L3_TrigExpense');

CREATE FUNCTION f_charges_amount_limit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.amount > 5000.00 THEN
    RAISE EXCEPTION 'Charge too large: %, max %', NEW.amount, 5000.00;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_charges_amount_limit
BEFORE INSERT ON charges
FOR EACH ROW
EXECUTE FUNCTION f_charges_amount_limit();
```

**Ожидаем:** триггер создан.  
**Почему:** `DROP IF EXISTS` убирает конфликт “trigger already exists”.

### 3.1.2 TEST OK

### Что делает блок (коротко):
Вставляем расход 5000.00 — должен пройти.

```sql
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (
  5000.00,
  CURRENT_DATE,
  (SELECT id FROM expense_items WHERE name='TEST_L3_TrigExpense' ORDER BY id DESC LIMIT 1)
);
```

**Ожидаем:** вставка проходит.  
**Почему:** условие запрета строго `> 5000.00`.

### 3.1.3 TEST FAIL

### Что делает блок (коротко):
Вставляем 5000.01 — должна быть ошибка. После ошибки делаем `ROLLBACK`.

```sql
BEGIN;

INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (
  5000.01,
  CURRENT_DATE,
  (SELECT id FROM expense_items WHERE name='TEST_L3_TrigExpense' ORDER BY id DESC LIMIT 1)
);

COMMIT;
```
- после ошибки выполнить:
```
ROLLBACK;
```

**Ожидаем:** ошибка `Charge too large...`.  
**Почему:** триггер блокирует запрещённую вставку.

---

## 3.2 BEFORE UPDATE ON sales: запрет менять продажи “в прошлом”

### 3.2.1 CREATE + SETUP

### Что делает блок (коротко):
Создаём триггер на UPDATE → создаём товар → добавляем 2 продажи (вчера и сегодня).

```sql
DROP TRIGGER IF EXISTS trg_sales_no_past_update ON sales;
DROP FUNCTION IF EXISTS f_sales_no_past_update();

CREATE FUNCTION f_sales_no_past_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD.sale_date < CURRENT_DATE THEN
    RAISE EXCEPTION 'Cannot update past sale (sale_date=%). Today=%', OLD.sale_date, CURRENT_DATE;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sales_no_past_update
BEFORE UPDATE ON sales
FOR EACH ROW
EXECUTE FUNCTION f_sales_no_past_update();

-- SETUP: товар + две продажи
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TEST_L3_TrigGood');

DELETE FROM warehouses WHERE name='TEST_L3_TrigGood';
INSERT INTO warehouses(name, quantity, amount) VALUES ('TEST_L3_TrigGood', 10, 10.00);

INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(11.00, 1, CURRENT_DATE - 1, (SELECT id FROM warehouses WHERE name='TEST_L3_TrigGood' ORDER BY id DESC LIMIT 1)),
(11.00, 1, CURRENT_DATE,     (SELECT id FROM warehouses WHERE name='TEST_L3_TrigGood' ORDER BY id DESC LIMIT 1));
```

**Ожидаем:** две продажи созданы.  
**Почему:** дальше покажем fail для “вчера” и ok для “сегодня”.

### 3.2.2 TEST FAIL (вчерашняя)

### Что делает блок (коротко):
Пытаемся обновить вчерашнюю продажу → ожидаем ошибку → `ROLLBACK`.

```sql
BEGIN;

UPDATE sales
SET amount = amount + 1.00
WHERE id = (
  SELECT id FROM sales
  WHERE sale_date = CURRENT_DATE - 1
  ORDER BY id DESC
  LIMIT 1
);

COMMIT;
```

- после ошибки:
```
ROLLBACK;
```

**Ожидаем:** ошибка `Cannot update past sale...`.  
**Почему:** `OLD.sale_date < CURRENT_DATE`.

### 3.2.3 TEST OK (сегодняшняя)

### Что делает блок (коротко):
Обновляем сегодняшнюю продажу → должно пройти.

```sql
UPDATE sales
SET amount = amount + 1.00
WHERE id = (
  SELECT id FROM sales
  WHERE sale_date = CURRENT_DATE
  ORDER BY id DESC
  LIMIT 1
);
```

**Ожидаем:** 1 row updated.  
**Почему:** дата продажи = текущая дата.

---

## 3.3 BEFORE DELETE ON charges: запрет удалять старые расходы (> 1 month)

### 3.3.1 CREATE + SETUP

### Что делает блок (коротко):
Создаём триггер на DELETE → создаём статью → добавляем 2 расхода: свежий и старый (40 дней назад).

```sql
DROP TRIGGER IF EXISTS trg_charges_no_delete_old ON charges;
DROP FUNCTION IF EXISTS f_charges_no_delete_old();

CREATE FUNCTION f_charges_no_delete_old()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD.charge_date < CURRENT_DATE - INTERVAL '1 month' THEN
    RAISE EXCEPTION 'Cannot delete old charge (charge_date=%).', OLD.charge_date;
  END IF;
  RETURN OLD;
END;
$$;

CREATE TRIGGER trg_charges_no_delete_old
BEFORE DELETE ON charges
FOR EACH ROW
EXECUTE FUNCTION f_charges_no_delete_old();

-- SETUP: статья + 2 расхода
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_DelExpense');

DELETE FROM expense_items WHERE name='TEST_L3_DelExpense';
INSERT INTO expense_items(name) VALUES ('TEST_L3_DelExpense');

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE,
 (SELECT id FROM expense_items WHERE name='TEST_L3_DelExpense' ORDER BY id DESC LIMIT 1)),
(10.00, CURRENT_DATE - INTERVAL '40 days',
 (SELECT id FROM expense_items WHERE name='TEST_L3_DelExpense' ORDER BY id DESC LIMIT 1));
```

**Ожидаем:** есть 2 расхода, один из них “старый”.  
**Почему:** дальше удаление “старого” должно упасть.

### 3.3.2 TEST OK (удаляем свежий)

### Что делает блок (коротко):
Удаляем расход сегодняшней датой — должен удалиться.

```sql
DELETE FROM charges
WHERE id = (
  SELECT c.id
  FROM charges c
  JOIN expense_items e ON e.id = c.expense_item_id
  WHERE e.name='TEST_L3_DelExpense'
    AND c.charge_date = CURRENT_DATE
  ORDER BY c.id DESC
  LIMIT 1
);
```

**Ожидаем:** 1 row deleted.  
**Почему:** расход не старше месяца.

### 3.3.3 TEST FAIL (удаляем старый)

### Что делает блок (коротко):
Пытаемся удалить “старый” расход — ожидаем ошибку → `ROLLBACK`.

```sql
BEGIN;

DELETE FROM charges
WHERE id = (
  SELECT c.id
  FROM charges c
  JOIN expense_items e ON e.id = c.expense_item_id
  WHERE e.name='TEST_L3_DelExpense'
    AND c.charge_date < CURRENT_DATE - INTERVAL '1 month'
  ORDER BY c.id DESC
  LIMIT 1
);

COMMIT;
```
- после ошибки:
```
ROLLBACK;
```

**Ожидаем:** ошибка `Cannot delete old charge...`.  
**Почему:** триггер блокирует удаление старых расходов.

---

# 4) CURSOR/циклы: прогноз прибыли на ближайший месяц

## 4.1 SETUP

### Что делает блок (коротко):
Создаём тестовый товар и статью расходов, добавляем по 4 записи на разные “месяцы” (10/40/70/110 дней назад), чтобы проверить веса 1/0.5/0.25.

```sql
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TEST_L3_CursorGood');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_CursorExpense');

DELETE FROM warehouses WHERE name='TEST_L3_CursorGood';
DELETE FROM expense_items WHERE name='TEST_L3_CursorExpense';

INSERT INTO warehouses(name, quantity, amount) VALUES ('TEST_L3_CursorGood', 1000, 10.00);
INSERT INTO expense_items(name) VALUES ('TEST_L3_CursorExpense');

INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(20.00, 1, CURRENT_DATE - INTERVAL '10 days',  (SELECT id FROM warehouses WHERE name='TEST_L3_CursorGood' ORDER BY id DESC LIMIT 1)),
(20.00, 1, CURRENT_DATE - INTERVAL '40 days',  (SELECT id FROM warehouses WHERE name='TEST_L3_CursorGood' ORDER BY id DESC LIMIT 1)),
(20.00, 1, CURRENT_DATE - INTERVAL '70 days',  (SELECT id FROM warehouses WHERE name='TEST_L3_CursorGood' ORDER BY id DESC LIMIT 1)),
(20.00, 1, CURRENT_DATE - INTERVAL '110 days', (SELECT id FROM warehouses WHERE name='TEST_L3_CursorGood' ORDER BY id DESC LIMIT 1));

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE - INTERVAL '10 days',  (SELECT id FROM expense_items WHERE name='TEST_L3_CursorExpense' ORDER BY id DESC LIMIT 1)),
(10.00, CURRENT_DATE - INTERVAL '40 days',  (SELECT id FROM expense_items WHERE name='TEST_L3_CursorExpense' ORDER BY id DESC LIMIT 1)),
(10.00, CURRENT_DATE - INTERVAL '70 days',  (SELECT id FROM expense_items WHERE name='TEST_L3_CursorExpense' ORDER BY id DESC LIMIT 1)),
(10.00, CURRENT_DATE - INTERVAL '110 days', (SELECT id FROM expense_items WHERE name='TEST_L3_CursorExpense' ORDER BY id DESC LIMIT 1));
```

**Ожидаем:** 4 продажи и 4 расхода вставились.  
**Почему:** это “крайние случаи” для разных весов по давности.

## 4.2 CREATE PROCEDURE

### Что делает блок (коротко):
Циклами обходим расходы/доходы за 4 месяца, применяем веса (1/0.5/0.25), считаем прибыль и возвращаем через OUT `profit`.

```sql
DROP PROCEDURE IF EXISTS p_forecast_profit_next_month(numeric);

CREATE PROCEDURE p_forecast_profit_next_month(OUT profit numeric)
LANGUAGE plpgsql
AS $$
DECLARE
  aver_expense numeric := 0;
  aver_income  numeric := 0;
  r_charge RECORD;
  r_sale   RECORD;
  w numeric;
BEGIN
  FOR r_charge IN
    SELECT c.amount, c.charge_date
    FROM charges c
    JOIN expense_items e ON e.id = c.expense_item_id
    WHERE c.charge_date >= CURRENT_DATE - INTERVAL '4 months'
      AND e.name = 'TEST_L3_CursorExpense'
  LOOP
    IF r_charge.charge_date >= CURRENT_DATE - INTERVAL '1 month' THEN
      w := 1.0;
    ELSIF r_charge.charge_date >= CURRENT_DATE - INTERVAL '2 months' THEN
      w := 0.5;
    ELSE
      w := 0.25;
    END IF;
    aver_expense := aver_expense + r_charge.amount * w;
  END LOOP;

  FOR r_sale IN
    SELECT (s.quantity * s.amount) AS money, s.sale_date
    FROM sales s
    JOIN warehouses w2 ON w2.id = s.warehouse_id
    WHERE s.sale_date >= CURRENT_DATE - INTERVAL '4 months'
      AND w2.name = 'TEST_L3_CursorGood'
  LOOP
    IF r_sale.sale_date >= CURRENT_DATE - INTERVAL '1 month' THEN
      w := 1.0;
    ELSIF r_sale.sale_date >= CURRENT_DATE - INTERVAL '2 months' THEN
      w := 0.5;
    ELSE
      w := 0.25;
    END IF;
    aver_income := aver_income + r_sale.money * w;
  END LOOP;

  profit := aver_income - aver_expense;
END;
$$;
```

**Ожидаем:** `CREATE PROCEDURE`.  
**Почему:** используем “курсорную” логику через `FOR ... IN SELECT ... LOOP`.

## 4.3 TEST

### Что делает блок (коротко):
Вызываем процедуру и смотрим `profit`.

```sql
CALL p_forecast_profit_next_month(NULL);
```

**Ожидаем:** `profit = 20`.  
**Почему:** доходы 20*(1+0.5+0.25+0.25)=40, расходы 10*(1+0.5+0.25+0.25)=20.

---

# 5) Ответ на теоретический вопрос: почему PROCEDURE, а не FUNCTION?

**Коротко:** в ЛР3 требуются **процедурные алгоритмы** и `OUT`-параметры (например, в 2.3 и прогнозе), поэтому логично использовать `PROCEDURE` и `CALL`.  
`FUNCTION` больше подходит, когда нужно вернуть значение и использовать в `SELECT` как часть запроса.
