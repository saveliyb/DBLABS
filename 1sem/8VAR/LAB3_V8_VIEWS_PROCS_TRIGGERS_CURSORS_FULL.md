# Лабораторная работа №3 — Представления, хранимые процедуры, триггеры и курсоры (PostgreSQL)
## Вариант 8: Автоматизация работы магазина

Этот файл — **шпаргалка для демонстрации** в pgAdmin:  
для каждого подпункта есть **Setup** (очистка/вставки под крайние случаи), затем **CREATE/TEST** блоки.  
Все тестовые сущности помечены префиксом `L3_...`.

> Внимание: этот файл **не удаляет ваши реальные данные**, чистит только тестовые (`name LIKE 'L3_%'`).

---

# 0) Подготовка (проверить таблицы)
```sql
SELECT
  to_regclass('public.warehouses')    AS warehouses,
  to_regclass('public.sales')         AS sales,
  to_regclass('public.charges')       AS charges,
  to_regclass('public.expense_items') AS expense_items;
```

---

# 1) Представления (VIEW)

## 1.1 VIEW: статьи расходов, по которым сумма за всё время > границы
**Требование:** «Создать представление, отображающее все статьи расхода, по которым за все время сумма превысила некоторую границу».

### Примечание про «границу»
В PostgreSQL **view не параметризуется**, поэтому границу фиксируем константой.  
В демонстрации используем `1000.00`. Если преподаватель попросит — меняется в одном месте.

### Setup (тестовые статьи + расходы)
Крайние случаи:
- сумма **ровно 1000** → не должна попасть при `>`  
- сумма **1000.01** → должна попасть  
- статья **без расходов** → не должна попасть

```sql
-- чистим только L3_ тестовые данные (дети -> родители)
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name LIKE 'L3_%');

DELETE FROM expense_items
WHERE name LIKE 'L3_%';

-- статьи
INSERT INTO expense_items(name) VALUES
('L3_OverLimit'),   -- будет 1000.01
('L3_ExactlyLimit'),-- будет 1000.00
('L3_NoCharges');   -- нет расходов

-- расходы: 1000.01
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(600.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_OverLimit' ORDER BY id DESC LIMIT 1)),
(400.01, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_OverLimit' ORDER BY id DESC LIMIT 1));

-- расходы: ровно 1000.00
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(700.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_ExactlyLimit' ORDER BY id DESC LIMIT 1)),
(300.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_ExactlyLimit' ORDER BY id DESC LIMIT 1));
```

### Создание VIEW
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

### Проверка (что показать)
```sql
SELECT * FROM v_expense_items_over_limit;
```
Ожидаемо: будет `L3_OverLimit`, не будет `L3_ExactlyLimit`, не будет `L3_NoCharges`.

---

## 1.2 VIEW: общее количество расходов за последний месяц по статьям
**Требование:** «Создать представление, отображающее общее количество расходов за последний месяц в разрезе статей расходов».

### Setup (крайние случаи)
- 2 расхода **в последнем месяце** → count=2  
- 1 расход **старше месяца** → не учитывается  
- статья без расходов → может появиться только при LEFT JOIN, но требование обычно про реально совершённые расходы → используем INNER JOIN

```sql
-- чистим тестовые L3_ данные для этого пункта (используем те же L3_ статьи)
DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name IN ('L3_MonthA','L3_MonthB'));

DELETE FROM expense_items
WHERE name IN ('L3_MonthA','L3_MonthB');

INSERT INTO expense_items(name) VALUES ('L3_MonthA'), ('L3_MonthB');

-- L3_MonthA: 2 записи в месяце + 1 старая
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_MonthA' ORDER BY id DESC LIMIT 1)),
(20.00, CURRENT_DATE - INTERVAL '10 days', (SELECT id FROM expense_items WHERE name='L3_MonthA' ORDER BY id DESC LIMIT 1)),
(30.00, CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM expense_items WHERE name='L3_MonthA' ORDER BY id DESC LIMIT 1));

-- L3_MonthB: 1 запись в месяце
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(15.00, CURRENT_DATE - INTERVAL '1 month', (SELECT id FROM expense_items WHERE name='L3_MonthB' ORDER BY id DESC LIMIT 1));
```

### Создание VIEW
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

### Проверка
```sql
SELECT * FROM v_expense_count_last_month_by_item
WHERE expense_item LIKE 'L3_%';
```

Ожидаемо:
- `L3_MonthA` будет count=2
- `L3_MonthB` будет count=1 (пограничная дата “ровно месяц назад” включается из-за `>=`)

---

# 2) Хранимые процедуры (PROCEDURE)

## 2.0 Теория (кратко): процедура vs функция и почему требуются процедуры
- **Функция (FUNCTION)** возвращает значение и может использоваться в `SELECT ...` как выражение.
- **Процедура (PROCEDURE)** вызывается командой `CALL`, **может управлять транзакциями** (COMMIT/ROLLBACK) и удобна для бизнес-операций “с побочными эффектами”.


## 2.0 Выбор языка SQL vs PL/pgSQL
- SQL-процедуры удобны для простых запросов.
- PL/pgSQL нужен, когда есть **переменные, условия, циклы, курсоры, OUT-параметры**.
В этой ЛР используются условия/курсор → выбираем **PL/pgSQL**.

---

## 2.1 Процедура без параметров: все товары + средняя стоимость их продаж за всё время
**Требование:** «процедура, выводящая все товары и среднюю стоимость их продаж за все время».

### Создание процедуры
```sql
DROP PROCEDURE IF EXISTS p_goods_avg_sale_price_all_time();

CREATE PROCEDURE p_goods_avg_sale_price_all_time()
LANGUAGE plpgsql
AS $$
BEGIN
  -- AVG по цене продажи за единицу (sales.amount)
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

### Проверка
```sql
CALL p_goods_avg_sale_price_all_time();
```

### Крайний случай
Товар без продаж → `avg_sale_price = 0` (из-за LEFT JOIN + COALESCE).

---

## 2.2 Процедура с входными параметрами: даты продаж, где 2 товара продавались одновременно
**Требование:** два параметра «товар1» и «товар2», вернуть **даты продаж**, когда оба продавались в один день.

### Setup (создаём 2 тестовых товара и продажи в одну дату/в разные даты)
```sql
-- чистим тестовые продажи и товары
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name IN ('L3_P1','L3_P2'));

DELETE FROM warehouses
WHERE name IN ('L3_P1','L3_P2');

INSERT INTO warehouses(name, quantity, amount) VALUES
('L3_P1', 100, 10.00),
('L3_P2', 100, 10.00);

-- оба проданы в один день (должно попасть)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(12.00, 1, CURRENT_DATE - INTERVAL '2 days', (SELECT id FROM warehouses WHERE name='L3_P1' ORDER BY id DESC LIMIT 1)),
(13.00, 1, CURRENT_DATE - INTERVAL '2 days', (SELECT id FROM warehouses WHERE name='L3_P2' ORDER BY id DESC LIMIT 1));

-- продан только один товар (не должно попасть)
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(12.00, 1, CURRENT_DATE - INTERVAL '1 days', (SELECT id FROM warehouses WHERE name='L3_P1' ORDER BY id DESC LIMIT 1));
```

### Создание процедуры
Процедура печатает результат через `SELECT` (как в прошлой), поэтому `CALL` покажет набор строк.

```sql
DROP PROCEDURE IF EXISTS p_dates_when_two_goods_sold_together(text, text);

CREATE PROCEDURE p_dates_when_two_goods_sold_together(IN good1 text, IN good2 text)
LANGUAGE plpgsql
AS $$
BEGIN
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

### Проверка
```sql
CALL p_dates_when_two_goods_sold_together('L3_P1','L3_P2');
```

### Крайние случаи
- Продажи “в один день” → дата есть
- Продан только один товар → даты нет

---

## 2.3 Процедура с OUT параметрами: доход и расход за период
**Требование:** вход `date1/date2`, выход `income_total/expense_total` за период.

### Setup (2 продажи, 2 расхода: один внутри периода, один вне)
```sql
-- чистим тестовые элементы (используем отдельные имена)
DELETE FROM sales
WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='L3_PeriodGood');

DELETE FROM charges
WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='L3_PeriodExpense');

DELETE FROM warehouses WHERE name='L3_PeriodGood';
DELETE FROM expense_items WHERE name='L3_PeriodExpense';

INSERT INTO warehouses(name, quantity, amount) VALUES ('L3_PeriodGood', 100, 10.00);
INSERT INTO expense_items(name) VALUES ('L3_PeriodExpense');

-- продажи: одна внутри, одна вне
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(20.00, 2, CURRENT_DATE - INTERVAL '5 days', (SELECT id FROM warehouses WHERE name='L3_PeriodGood' ORDER BY id DESC LIMIT 1)), -- income=40
(20.00, 2, CURRENT_DATE - INTERVAL '50 days', (SELECT id FROM warehouses WHERE name='L3_PeriodGood' ORDER BY id DESC LIMIT 1)); -- вне

-- расходы: один внутри, один вне
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(15.00, CURRENT_DATE - INTERVAL '7 days', (SELECT id FROM expense_items WHERE name='L3_PeriodExpense' ORDER BY id DESC LIMIT 1)),
(15.00, CURRENT_DATE - INTERVAL '70 days', (SELECT id FROM expense_items WHERE name='L3_PeriodExpense' ORDER BY id DESC LIMIT 1));
```

### Создание процедуры
Интервал: считаем включительно обе границы (>= date1 AND <= date2).

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

### Проверка
```sql
CALL p_income_expense_for_period(CURRENT_DATE - INTERVAL '10 days', CURRENT_DATE);
```

Ожидаемо:
- income_total = 40.00 (только продажа 5 дней назад)
- expense_total = 15.00 (только расход 7 дней назад)

---

# 3) Триггеры

## 3.0 Теория: FOR EACH ROW vs FOR EACH STATEMENT
- `FOR EACH ROW` срабатывает **для каждой строки** (подходит для проверки значений каждой вставляемой/изменяемой строки).
- `FOR EACH STATEMENT` срабатывает **один раз на оператор** (подходит для логики уровня запроса).  
В этой ЛР нужны проверки по каждой строке → используем **FOR EACH ROW**.

---

## 3.1 Триггер на INSERT в charges: запрет суммы расхода больше заданной
**Требование:** «не позволяет добавлять расход, с суммой большей заданной».

Граница в триггере: `5000.00` (можно поменять).

### Создание функции-триггера и триггера
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

### Проверка (2 крайних случая)
```sql
-- подготовка тестовой статьи
DELETE FROM charges WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='L3_TrigExpense');
DELETE FROM expense_items WHERE name='L3_TrigExpense';
INSERT INTO expense_items(name) VALUES ('L3_TrigExpense');

-- OK: 5000.00 (должно вставиться)
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (5000.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_TrigExpense' ORDER BY id DESC LIMIT 1));

-- FAIL: 5000.01 (должна быть ошибка, вставки не будет)
INSERT INTO charges(amount, charge_date, expense_item_id)
VALUES (5000.01, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_TrigExpense' ORDER BY id DESC LIMIT 1));
```

---

## 3.2 Триггер на UPDATE sales: запрет менять продажи “задним числом”
**Требование:** «не позволяет изменять данные в таблице продаж задним числом от сегодняшней даты».

Интерпретация (обычная): **нельзя изменять строку**, если `sale_date < CURRENT_DATE`.

### Создание
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

### Проверка (крайние случаи)
```sql
-- подготовка тестового товара и 2 продаж: вчера и сегодня
DELETE FROM sales WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='L3_TrigGood');
DELETE FROM warehouses WHERE name='L3_TrigGood';

INSERT INTO warehouses(name, quantity, amount) VALUES ('L3_TrigGood', 10, 10.00);

INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(11.00, 1, CURRENT_DATE - INTERVAL '1 day', (SELECT id FROM warehouses WHERE name='L3_TrigGood' ORDER BY id DESC LIMIT 1)), -- вчера
(11.00, 1, CURRENT_DATE,                 (SELECT id FROM warehouses WHERE name='L3_TrigGood' ORDER BY id DESC LIMIT 1));    -- сегодня

-- FAIL: пытаемся изменить "вчерашнюю" продажу (должна быть ошибка)
UPDATE sales
SET amount = amount + 1.00
WHERE id = (
  SELECT id FROM sales WHERE sale_date = CURRENT_DATE - INTERVAL '1 day' ORDER BY id DESC LIMIT 1
);

-- OK: меняем сегодняшнюю (должно пройти)
UPDATE sales
SET amount = amount + 1.00
WHERE id = (
  SELECT id FROM sales WHERE sale_date = CURRENT_DATE ORDER BY id DESC LIMIT 1
);
```

---

## 3.3 Триггер на DELETE charges: если расход старше месяца — откат транзакции
**Требование:** «при удалении расхода, если расход был более чем месяц назад, откатывает транзакцию».

В PostgreSQL “откат” делается через `RAISE EXCEPTION` → удаление не произойдёт, транзакция станет aborted.

### Создание
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

### Проверка (2 крайних случая)
```sql
-- подготовим 2 расхода: сегодня и 40 дней назад
DELETE FROM charges WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='L3_DelExpense');
DELETE FROM expense_items WHERE name='L3_DelExpense';
INSERT INTO expense_items(name) VALUES ('L3_DelExpense');

INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name='L3_DelExpense' ORDER BY id DESC LIMIT 1)),
(10.00, CURRENT_DATE - INTERVAL '40 days', (SELECT id FROM expense_items WHERE name='L3_DelExpense' ORDER BY id DESC LIMIT 1));

-- OK: удаляем "сегодняшний" (должно пройти)
DELETE FROM charges
WHERE id = (SELECT c.id
            FROM charges c
            JOIN expense_items e ON e.id=c.expense_item_id
            WHERE e.name='L3_DelExpense' AND c.charge_date = CURRENT_DATE
            ORDER BY c.id DESC LIMIT 1);

-- FAIL: удаляем старый (должна быть ошибка)
DELETE FROM charges
WHERE id = (SELECT c.id
            FROM charges c
            JOIN expense_items e ON e.id=c.expense_item_id
            WHERE e.name='L3_DelExpense' AND c.charge_date < CURRENT_DATE - INTERVAL '1 month'
            ORDER BY c.id DESC LIMIT 1);

-- после ошибки выполнить:
-- ROLLBACK;
```

---

# 4) Курсоры: процедура расчёта предполагаемой прибыли на ближайший месяц
**Требование:** одна OUT переменная profit. Алгоритм: веса по месяцам за последние 4 месяца: 1, 1/2, 1/4.  
Интерпретация:
- если дата попадает в **последний месяц** → вес 1
- если дата попадает в **предыдущий месяц** (1–2 месяца назад) → вес 0.5
- иначе (2–4 месяца назад) → вес 0.25

## 4.1 Setup (продажи и расходы за последние 4 месяца)
```sql
-- чистим курсорные тесты
DELETE FROM sales WHERE warehouse_id IN (SELECT id FROM warehouses WHERE name='L3_CursorGood');
DELETE FROM charges WHERE expense_item_id IN (SELECT id FROM expense_items WHERE name='L3_CursorExpense');
DELETE FROM warehouses WHERE name='L3_CursorGood';
DELETE FROM expense_items WHERE name='L3_CursorExpense';

INSERT INTO warehouses(name, quantity, amount) VALUES ('L3_CursorGood', 1000, 10.00);
INSERT INTO expense_items(name) VALUES ('L3_CursorExpense');

-- 4 интервала: 10 дней, 40 дней, 70 дней, 110 дней назад
-- sales: money = quantity*amount
INSERT INTO sales(amount, quantity, sale_date, warehouse_id) VALUES
(20.00, 1, CURRENT_DATE - INTERVAL '10 days',  (SELECT id FROM warehouses WHERE name='L3_CursorGood' ORDER BY id DESC LIMIT 1)),  -- weight 1
(20.00, 1, CURRENT_DATE - INTERVAL '40 days',  (SELECT id FROM warehouses WHERE name='L3_CursorGood' ORDER BY id DESC LIMIT 1)),  -- weight 0.5
(20.00, 1, CURRENT_DATE - INTERVAL '70 days',  (SELECT id FROM warehouses WHERE name='L3_CursorGood' ORDER BY id DESC LIMIT 1)),  -- weight 0.25
(20.00, 1, CURRENT_DATE - INTERVAL '110 days', (SELECT id FROM warehouses WHERE name='L3_CursorGood' ORDER BY id DESC LIMIT 1));  -- weight 0.25

-- charges: amount
INSERT INTO charges(amount, charge_date, expense_item_id) VALUES
(10.00, CURRENT_DATE - INTERVAL '10 days',  (SELECT id FROM expense_items WHERE name='L3_CursorExpense' ORDER BY id DESC LIMIT 1)), -- weight 1
(10.00, CURRENT_DATE - INTERVAL '40 days',  (SELECT id FROM expense_items WHERE name='L3_CursorExpense' ORDER BY id DESC LIMIT 1)), -- weight 0.5
(10.00, CURRENT_DATE - INTERVAL '70 days',  (SELECT id FROM expense_items WHERE name='L3_CursorExpense' ORDER BY id DESC LIMIT 1)), -- weight 0.25
(10.00, CURRENT_DATE - INTERVAL '110 days', (SELECT id FROM expense_items WHERE name='L3_CursorExpense' ORDER BY id DESC LIMIT 1)); -- weight 0.25
```

## 4.2 Создание процедуры с курсорами
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
  -- расходы за последние 4 месяца
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

  -- доходы за последние 4 месяца
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

## 4.3 Проверка
```sql
CALL p_forecast_profit_next_month(NULL);
```

Ожидаемо (на тестовых данных):
- доходы: 20*(1 + 0.5 + 0.25 + 0.25) = 20*2.0 = 40
- расходы: 10*(1 + 0.5 + 0.25 + 0.25) = 10*2.0 = 20
- profit = 20

---

# 5) Быстрый список созданных объектов (по желанию)
```sql
SELECT schemaname, viewname
FROM pg_views
WHERE schemaname='public' AND viewname IN ('v_expense_items_over_limit','v_expense_count_last_month_by_item');

SELECT proname, prokind
FROM pg_proc
WHERE proname LIKE 'p_%' OR proname LIKE 'f_%'
ORDER BY proname;

SELECT tgname, tgrelid::regclass AS table_name
FROM pg_trigger
WHERE NOT tgisinternal
ORDER BY tgname;
```

---

# 6) Ответы на “вопросы ЛР3” (коротко, для устной защиты)

- **Почему процедуры, а не функции?** Процедуры вызываются `CALL` и подходят для бизнес-операций; в PostgreSQL процедуры могут управлять транзакциями, а функции — чаще для вычислений внутри запросов.
- **Почему PL/pgSQL?** Нужны переменные, условия, циклы и курсоры → SQL-язык не подходит.
- **FOR EACH ROW vs FOR EACH STATEMENT:** row-триггер для проверки каждой строки (как в этой ЛР), statement-триггер — один раз на запрос.
