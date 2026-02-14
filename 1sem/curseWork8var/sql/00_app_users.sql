-- Создаёт таблицу пользователей приложения и добавляет двух демонстрационных пользователей.
-- Пароли для демонстрации (plaintext):
-- admin -> admin123
-- operator -> operator123

CREATE TABLE IF NOT EXISTS app_users(
  id bigserial PRIMARY KEY,
  login text UNIQUE NOT NULL,
  pass_hash text NOT NULL,
  role text NOT NULL CHECK (role in ('admin','operator'))
);

-- Значения с уже вычисленными Argon2-hash (сгенерированы локально):
INSERT INTO app_users (login, pass_hash, role) VALUES
  ('admin', '$argon2id$v=19$m=65536,t=3,p=4$ucPlhnQFzOJr3m899xZKPg$lCfvTfCwnmz7iDL/d+8AucM0kojsJXlnFFYvfUfpEow', 'admin')
ON CONFLICT (login) DO NOTHING;

INSERT INTO app_users (login, pass_hash, role) VALUES
  ('operator', '$argon2id$v=19$m=65536,t=3,p=4$UMBT5elaBPnXtHu5pDmMfQ$JPMu4SCtQZWMASe5bNsJAZ5cF3pQG8/7QYAB5DNFla4', 'operator')
ON CONFLICT (login) DO NOTHING;
