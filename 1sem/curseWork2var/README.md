Library GUI client — CP1

Установка зависимостей

```bash
python -m pip install -r requirements.txt
```

Создание конфига

Скопируйте `config.ini.example` в `config.ini` и отредактируйте параметры PostgreSQL.

Формат `config.ini.example`:

[postgres]
host=127.0.0.1
port=5432
# Library Client (PySide6 + PostgreSQL)

Краткое руководство по запуску и настройке проекта.

Prerequisites
- Python 3.10+
- Postgres server with a database available

Создание виртуального окружения и установка зависимостей

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Запуск приложения

```bash
python -m app
```

Настройка Postgres
- Основной файл конфигурации: `app/config.py` — редактируйте параметры подключения к базе там.
- Проект может также поддерживать чтение параметров из переменных окружения (см. `app/config.py`).

Роли
- admin: полный доступ к справочникам (Clients, Books, Book Types), журналу выдач и отчётам.
- user: ограниченный доступ (просмотр, операции в рамках прав).

Отчёты
- В меню: **ОТЧЕТЫ → Активные выдачи** и **ОТЧЕТЫ → Штрафы**

Если нужно — добавьте сюда примеры конфигурации или сниппеты подключения к Postgres из `app/config.py`.
