# Лабораторная работа №1 — SQL-DDL (PostgreSQL)
## Вариант 8: Автоматизация работы магазина

Файл предназначен для демонстрации:  
1) Создание таблиц  
2) Создание ограничений  
3) Заполнение таблиц  
4) Проверка связей и данных  

Все блоки можно копировать напрямую в pgAdmin.

---

# 1. Создание таблиц (DDL)

## 1.1 Таблица warehouses (товары на складе)

```sql
CREATE TABLE IF NOT EXISTS warehouses (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name     text NOT NULL,
    quantity integer NOT NULL CHECK (quantity >= 0),
    amount   numeric(18,2) NOT NULL CHECK (amount >= 0)
);
```

Пояснение:
- id — автоинкремент (IDENTITY)
- quantity >= 0 — нельзя отрицательное количество
- amount >= 0 — цена не может быть отрицательной

---

## 1.2 Таблица expense_items (статьи расходов)

```sql
CREATE TABLE IF NOT EXISTS expense_items (
    id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL
);
```

---

## 1.3 Таблица sales (продажи)

```sql
CREATE TABLE IF NOT EXISTS sales (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    amount       numeric(18,2) NOT NULL CHECK (amount >= 0),
    quantity     integer NOT NULL CHECK (quantity > 0),
    sale_date    date NOT NULL,
    warehouse_id bigint NOT NULL
);
```

---

## 1.4 Таблица charges (расходы)

```sql
CREATE TABLE IF NOT EXISTS charges (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    amount          numeric(18,2) NOT NULL CHECK (amount >= 0),
    charge_date     date NOT NULL,
    expense_item_id bigint NOT NULL
);
```

---

# 2. Создание внешних ключей

```sql
ALTER TABLE sales
    ADD CONSTRAINT fk_sales_warehouses
    FOREIGN KEY (warehouse_id)
    REFERENCES warehouses(id)
    ON DELETE CASCADE;
```

```sql
ALTER TABLE charges
    ADD CONSTRAINT fk_charges_expense_items
    FOREIGN KEY (expense_item_id)
    REFERENCES expense_items(id)
    ON DELETE CASCADE;
```

---

# 3. Заполнение таблиц

## 3.1 Очистка данных

```sql
DELETE FROM sales;
DELETE FROM charges;
DELETE FROM warehouses;
DELETE FROM expense_items;
```

## 3.2 warehouses

```sql
INSERT INTO warehouses (name, quantity, amount) VALUES
('Milk 1L', 100, 1.20),
('Bread',   50,  0.80),
('Coffee',  20,  5.50);
```

## 3.3 expense_items

```sql
INSERT INTO expense_items (name) VALUES
('Salary'),
('Rent'),
('Delivery');
```

## 3.4 sales

```sql
INSERT INTO sales (amount, quantity, sale_date, warehouse_id) VALUES
(1.50, 10, CURRENT_DATE, (SELECT id FROM warehouses WHERE name = 'Milk 1L')),
(1.10,  5, CURRENT_DATE, (SELECT id FROM warehouses WHERE name = 'Bread')),
(6.50,  2, CURRENT_DATE, (SELECT id FROM warehouses WHERE name = 'Coffee'));
```

## 3.5 charges

```sql
INSERT INTO charges (amount, charge_date, expense_item_id) VALUES
(2000.00, CURRENT_DATE, (SELECT id FROM expense_items WHERE name = 'Salary')),
(800.00,  CURRENT_DATE, (SELECT id FROM expense_items WHERE name = 'Rent'));
```

---

# 4. Проверка данных

## 4.1 Проверка таблиц

```sql
SELECT * FROM warehouses ORDER BY id;
SELECT * FROM expense_items ORDER BY id;
SELECT * FROM charges ORDER BY id;
```

## 4.2 Проверка sales ↔ warehouses

```sql
SELECT
    s.id,
    w.name AS good_name,
    s.quantity,
    s.amount,
    s.sale_date
FROM sales s
JOIN warehouses w ON w.id = s.warehouse_id
ORDER BY s.id;
```

## 4.3 Проверка charges ↔ expense_items

```sql
SELECT
    c.id,
    e.name AS expense_item,
    c.amount,
    c.charge_date
FROM charges c
JOIN expense_items e ON e.id = c.expense_item_id
ORDER BY c.id;
```

---

# 5. Теоретические вопросы

## Что такое DDL?
DDL (Data Definition Language) — язык определения данных:
CREATE, ALTER, DROP.

## PRIMARY KEY
Уникальный идентификатор записи.
Не может быть NULL.

## FOREIGN KEY
Обеспечивает ссылочную целостность между таблицами.
Может иметь ON DELETE CASCADE.

## Ограничения (CONSTRAINT)
NOT NULL — значение обязательно.
CHECK — логическое условие.
PRIMARY KEY — уникальность.
FOREIGN KEY — связь таблиц.


