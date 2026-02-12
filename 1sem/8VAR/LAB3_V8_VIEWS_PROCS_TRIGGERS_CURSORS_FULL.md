# Лабораторная работа №3 — VIEW / FUNCTION / PROCEDURE / TRIGGER / CURSOR (PostgreSQL)
## Вариант 8 — Автоматизация работы магазина

Это **рабочий** файл для демонстрации в pgAdmin: каждый пункт = **SETUP → CREATE → TEST**.  
Все тестовые данные имеют единый префикс: **`TEST_L3_`** (ничего “чужого” не трогаем).

> Важно: в PostgreSQL **PROCEDURE не может “просто вывести SELECT”** (как ты пытался) — поэтому пункты 2.1/2.2 сделаны как **FUNCTION**, чтобы их можно было красиво показать через `SELECT * FROM ...`.

---

# 0) Полная очистка тестовых данных ЛР3 (безопасно)
```sql
-- дети
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name LIKE 'TEST_L3_%');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'TEST_L3_%');

-- родители
DELETE FROM warehouses WHERE name LIKE 'TEST_L3_%';
DELETE FROM expense_items WHERE name LIKE 'TEST_L3_%';
```

Проверка таблиц:
```sql
SELECT
  to_regclass('public.warehouses')    AS warehouses,
  to_regclass('public.sales')         AS sales,
  to_regclass('public.charges')       AS charges,
  to_regclass('public.expense_items') AS expense_items;
```

---

# 1) Представления (VIEW)

## 1.1 VIEW: статьи расходов, где сумма расходов за всё время > 1000.00
### SETUP (крайние случаи: >, =, нет расходов)
```sql
-- очистка тестовых расходов/статей по этому пункту
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name IN ('TEST_L3_OverLimit','TEST_L3_ExactlyLimit','TEST_L3_NoCharges'));

DELETE FROM expense_items
WHERE name IN ('TEST_L3_OverLimit','TEST_L3_ExactlyLimit','TEST_L3_NoCharges');

-- статьи
INSERT INTO expense_items(name) VALUES
('TEST_L3_OverLimit'),
('TEST_L3_ExactlyLimit'),
('TEST_L3_NoCharges');

-- OverLimit = 1000.01 (должна попасть)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(600.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_OverLimit' ORDER BY id DESC LIMIT 1)),
(400.01, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_OverLimit' ORDER BY id DESC LIMIT 1));

-- ExactlyLimit = 1000.00 (НЕ должна попасть при HAVING > 1000)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(700.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_ExactlyLimit' ORDER BY id DESC LIMIT 1)),
(300.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_ExactlyLimit' ORDER BY id DESC LIMIT 1));
```

### CREATE VIEW
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

### TEST (показываем только тестовые строки)
```sql
SELECT *
FROM v_expense_items_over_limit
WHERE expense_item LIKE 'TEST_L3_%'
ORDER BY total_amount DESC;
```

Ожидаемо:
- есть `TEST_L3_OverLimit`
- нет `TEST_L3_ExactlyLimit`
- нет `TEST_L3_NoCharges` (у него нет расходов → JOIN не даёт строк)

---

## 1.2 VIEW: количество расходов за последний месяц в разрезе статей
### SETUP (крайние случаи: 2 в месяце, 1 старше месяца, граница = 1 month)
```sql
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name IN ('TEST_L3_MonthA','TEST_L3_MonthB'));

DELETE FROM expense_items
WHERE name IN ('TEST_L3_MonthA','TEST_L3_MonthB');

INSERT INTO expense_items(name) VALUES ('TEST_L3_MonthA'), ('TEST_L3_MonthB');

-- MonthA: 2 внутри месяца + 1 старый (не должен учитываться)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_MonthA' ORDER BY id DESC LIMIT 1)),
(20.00, CURRENT_DATE - INTERVAL '10 days', (SELECT id FROM expense_items WHERE name='TEST_L3_MonthA' ORDER BY id DESC LIMIT 1)),
(30.00, CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM expense_items WHERE name='TEST_L3_MonthA' ORDER BY id DESC LIMIT 1));

-- MonthB: ровно 1 month назад (включается из-за >=)
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(15.00, CURRENT_DATE - INTERVAL '1 month', (SELECT id FROM expense_items WHERE name='TEST_L3_MonthB' ORDER BY id DESC LIMIT 1));
```

### CREATE VIEW
```sql
DROP VIEW IF EXISTS v_expense_count_last_month_by_item;

CREATE VIEW v_expense_count_last_month_by_item AS
SELECT
  e.id,
  e.name AS expense_item,
  COUNT(*) AS charges_count_last_month
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
WHERE c.charge_date >= CURRENT_DATE - INTERVAL '1 month'
GROUP BY e.id, e.name
ORDER BY charges_count_last_month DESC, e.name;
```

### TEST
```sql
SELECT *
FROM v_expense_count_last_month_by_item
WHERE expense_item LIKE 'TEST_L3_%'
ORDER BY charges_count_last_month DESC, expense_item;
```

Ожидаемо:
- `TEST_L3_MonthA` = 2
- `TEST_L3_MonthB` = 1

---

# 2) Подпрограммы

## 2.1 (Вместо “процедуры”) FUNCTION: товары + средняя цена их продаж за всё время
### Почему FUNCTION
В PostgreSQL `CALL procedure()` **не может возвращать табличный результат через SELECT**. Для “вывода таблицы” корректно использовать `FUNCTION ... RETURNS TABLE ... RETURN QUERY`.

### CREATE FUNCTION
```sql
DROP FUNCTION IF EXISTS f_goods_avg_sale_price_all_time();

CREATE FUNCTION f_goods_avg_sale_price_all_time()
RETURNS TABLE (
  id bigint,
  name text,
  avg_sale_price numeric
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    w.id,
    w.name,
    COALESCE(AVG(s.amount), 0) AS avg_sale_price
  FROM warehouses w
  LEFT JOIN sales s ON s.warehouse_id = w.id
  GROUP BY w.id, w.name
  ORDER BY w.id;
END;
$$;
```

### TEST
```sql
SELECT * FROM f_goods_avg_sale_price_all_time()
ORDER BY id;
```

---

## 2.2 (Вместо “процедуры”) FUNCTION: даты, когда 2 товара продавались в один день
### SETUP (2 товара, 1 общая дата, 1 дата только одного)
```sql
-- чистим тестовые товары + продажи
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name IN ('TEST_L3_P1','TEST_L3_P2'));

DELETE FROM warehouses
WHERE name IN ('TEST_L3_P1','TEST_L3_P2');

INSERT INTO warehouses(name, quantity, amount) VALUES
('TEST_L3_P1', 100, 10.00),
('TEST_L3_P2', 100, 10.00);

-- общая дата (должна попасть)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(12.00, 1, (CURRENT_DATE - 2), (SELECT id FROM warehouses WHERE name='TEST_L3_P1' ORDER BY id DESC LIMIT 1)),
(13.00, 1, (CURRENT_DATE - 2), (SELECT id FROM warehouses WHERE name='TEST_L3_P2' ORDER BY id DESC LIMIT 1));

-- дата только одного товара (не должна попасть)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(12.00, 1, (CURRENT_DATE - 1), (SELECT id FROM warehouses WHERE name='TEST_L3_P1' ORDER BY id DESC LIMIT 1));
```

### CREATE FUNCTION
```sql
DROP FUNCTION IF EXISTS f_dates_when_two_goods_sold_together(text, text);

CREATE FUNCTION f_dates_when_two_goods_sold_together(good1 text, good2 text)
RETURNS TABLE (sale_date date)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
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
  ORDER BY s1.sale_date;
END;
$$;
```

### TEST
```sql
SELECT * FROM f_dates_when_two_goods_sold_together('TEST_L3_P1','TEST_L3_P2');
```

Ожидаемо: одна строка с датой `CURRENT_DATE - 2`.

---

## 2.3 PROCEDURE с OUT: доход и расход за период (date1..date2)
### SETUP (одна продажа/расход в периоде, одна вне)
```sql
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TEST_L3_PeriodGood');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_PeriodExpense');

DELETE FROM warehouses WHERE name='TEST_L3_PeriodGood';
DELETE FROM expense_items WHERE name='TEST_L3_PeriodExpense';

INSERT INTO warehouses(name, quantity, amount) VALUES ('TEST_L3_PeriodGood', 100, 10.00);
INSERT INTO expense_items(name) VALUES ('TEST_L3_PeriodExpense');

-- В периоде (последние 10 дней)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(20.00, 2, CURRENT_DATE - 5, (SELECT id FROM warehouses WHERE name='TEST_L3_PeriodGood' ORDER BY id DESC LIMIT 1)); -- income=40

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(15.00, CURRENT_DATE - 7, (SELECT id FROM expense_items WHERE name='TEST_L3_PeriodExpense' ORDER BY id DESC LIMIT 1)); -- expense=15

-- ВНЕ периода
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(20.00, 2, CURRENT_DATE - 50, (SELECT id FROM warehouses WHERE name='TEST_L3_PeriodGood' ORDER BY id DESC LIMIT 1));

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(15.00, CURRENT_DATE - 70, (SELECT id FROM expense_items WHERE name='TEST_L3_PeriodExpense' ORDER BY id DESC LIMIT 1));
```

### CREATE PROCEDURE
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
  SELECT COALESCE(SUM(quantity * amount), 0)
    INTO income_total
  FROM sales
  WHERE sale_date >= date1
    AND sale_date <= date2;

  SELECT COALESCE(SUM(amount), 0)
    INTO expense_total
  FROM charges
  WHERE charge_date >= date1
    AND charge_date <= date2;
END;
$$;
```

### TEST (ВАЖНО: передаём DATE, не timestamp)
```sql
CALL p_income_expense_for_period(CURRENT_DATE - 10, CURRENT_DATE, NULL, NULL);
```

Ожидаемо:
- income_total = 40
- expense_total = 15

---

# 3) Триггеры (TRIGGER)

## 3.1 BEFORE INSERT ON charges: запрет amount > 5000
### CREATE
```sql
DROP TRIGGER IF EXISTS trg_charges_amount_limit ON charges;
DROP FUNCTION IF EXISTS f_charges_amount_limit();

CREATE FUNCTION f_charges_amount_limit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.amount > 5000.00 THEN
    RAISE EXCEPTION 'Charge amount too large: %, max %', NEW.amount, 5000.00;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_charges_amount_limit
BEFORE INSERT ON charges
FOR EACH ROW
EXECUTE FUNCTION f_charges_amount_limit();
```

### TEST (крайние случаи =5000 ок, 5000.01 ошибка)
```sql
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_TrigExpense');

DELETE FROM expense_items WHERE name='TEST_L3_TrigExpense';
INSERT INTO expense_items(name) VALUES ('TEST_L3_TrigExpense');

-- OK
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (5000.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_TrigExpense' ORDER BY id DESC LIMIT 1));

-- FAIL (будет ошибка)
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (5000.01, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_TrigExpense' ORDER BY id DESC LIMIT 1));
```

---

## 3.2 BEFORE UPDATE ON sales: запрет менять продажи задним числом
### CREATE
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
```

### TEST
```sql
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TEST_L3_TrigGood');

DELETE FROM warehouses WHERE name='TEST_L3_TrigGood';
INSERT INTO warehouses(name, quantity, amount) VALUES ('TEST_L3_TrigGood', 10, 10.00);

-- вчера и сегодня
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(11.00, 1, CURRENT_DATE - 1, (SELECT id FROM warehouses WHERE name='TEST_L3_TrigGood' ORDER BY id DESC LIMIT 1)),
(11.00, 1, CURRENT_DATE,     (SELECT id FROM warehouses WHERE name='TEST_L3_TrigGood' ORDER BY id DESC LIMIT 1));

-- FAIL: пытаемся изменить вчерашнюю
UPDATE sales
SET amount = amount + 1.00
WHERE id = (
  SELECT id FROM sales
  WHERE sale_date = CURRENT_DATE - 1
  ORDER BY id DESC
  LIMIT 1
);

-- OK: меняем сегодняшнюю
UPDATE sales
SET amount = amount + 1.00
WHERE id = (
  SELECT id FROM sales
  WHERE sale_date = CURRENT_DATE
  ORDER BY id DESC
  LIMIT 1
);
```

---

## 3.3 BEFORE DELETE ON charges: если расход старше месяца — запрет (ошибка)
### CREATE
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
```

### TEST (делаем в транзакции, чтобы после ошибки быстро восстановиться)
```sql
-- подготовка
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_DelExpense');
DELETE FROM expense_items WHERE name='TEST_L3_DelExpense';
INSERT INTO expense_items(name) VALUES ('TEST_L3_DelExpense');

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='TEST_L3_DelExpense' ORDER BY id DESC LIMIT 1)),
(10.00, CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM expense_items WHERE name='TEST_L3_DelExpense' ORDER BY id DESC LIMIT 1));

BEGIN;

-- OK: удаляем свежий
DELETE FROM charges
WHERE id = (
  SELECT c.id
  FROM charges c
  JOIN expense_items e ON e.id=c.expense_item_id
  WHERE e.name='TEST_L3_DelExpense' AND c.charge_date = CURRENT_DATE
  ORDER BY c.id DESC
  LIMIT 1
);

-- FAIL: пытаемся удалить старый (будет ошибка)
DELETE FROM charges
WHERE id = (
  SELECT c.id
  FROM charges c
  JOIN expense_items e ON e.id=c.expense_item_id
  WHERE e.name='TEST_L3_DelExpense' AND c.charge_date < CURRENT_DATE - INTERVAL '1 month'
  ORDER BY c.id DESC
  LIMIT 1
);

COMMIT; -- не выполнится из-за ошибки
```

После ошибки выполнить:
```sql
ROLLBACK;
```

---

# 4) Курсоры: прогноз прибыли на ближайший месяц (OUT profit)
Алгоритм (как в методичке): веса по месяцам за последние 4 месяца: **1, 1/2, 1/4**.

## 4.1 SETUP (продажи и расходы за 4 месяца)
```sql
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='TEST_L3_CursorGood');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='TEST_L3_CursorExpense');

DELETE FROM warehouses WHERE name='TEST_L3_CursorGood';
DELETE FROM expense_items WHERE name='TEST_L3_CursorExpense';

INSERT INTO warehouses(name, quantity, amount) VALUES ('TEST_L3_CursorGood', 1000, 10.00);
INSERT INTO expense_items(name) VALUES ('TEST_L3_CursorExpense');

-- 10, 40, 70, 110 дней назад
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

## 4.2 CREATE PROCEDURE (с курсорами/циклами)
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
  -- расходы
  FOR r_charge IN
    SELECT amount, charge_date
    FROM charges
    WHERE charge_date >= CURRENT_DATE - INTERVAL '4 months'
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

  -- доходы
  FOR r_sale IN
    SELECT (quantity * amount) AS money, sale_date
    FROM sales
    WHERE sale_date >= CURRENT_DATE - INTERVAL '4 months'
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

## 4.3 TEST
```sql
CALL p_forecast_profit_next_month(NULL);
```

Ожидаемо на тестовых данных:
- доход: 20*(1 + 0.5 + 0.25 + 0.25) = 40
- расход: 10*(1 + 0.5 + 0.25 + 0.25) = 20
- profit = 20

---

# 5) Быстрый список созданных объектов (по желанию)
```sql
SELECT schemaname, viewname
FROM pg_views
WHERE schemaname='public'
  AND viewname IN ('v_expense_items_over_limit','v_expense_count_last_month_by_item');

SELECT proname, prokind
FROM pg_proc
WHERE proname IN (
  'f_goods_avg_sale_price_all_time',
  'f_dates_when_two_goods_sold_together',
  'p_income_expense_for_period',
  'p_forecast_profit_next_month',
  'f_charges_amount_limit',
  'f_sales_no_past_update',
  'f_charges_no_delete_old'
)
ORDER BY proname;

SELECT tgname, tgrelid::regclass AS table_name
FROM pg_trigger
WHERE NOT tgisinternal
ORDER BY tgname;
```

---

# 6) Ответы на вопросы (кратко для защиты)
- **Почему FUNCTION вместо PROCEDURE в пунктах 2.1/2.2?** Потому что `FUNCTION` может вернуть табличный результат через `RETURN QUERY` и удобно показывается `SELECT * FROM ...`. В `PROCEDURE` простой `SELECT` внутри даёт ошибку “no destination for result data”.
- **Почему PL/pgSQL?** Нужны переменные, условия, циклы/курсорная обработка.
- **FOR EACH ROW vs FOR EACH STATEMENT:** row-триггер срабатывает на каждую строку (проверки значений), statement — один раз на запрос.
