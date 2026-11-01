CREATE TABLE IF NOT EXISTS breeds (
 id SERIAL PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS shelters (
 id SERIAL PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE, city VARCHAR(120) NOT NULL
);
CREATE TABLE IF NOT EXISTS dogs (
 id SERIAL PRIMARY KEY, name VARCHAR(120) NOT NULL,
 age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 30),
 breed_id INTEGER NOT NULL REFERENCES breeds(id),
 shelter_id INTEGER NOT NULL REFERENCES shelters(id),
 status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available','adopted'))
);
CREATE TABLE IF NOT EXISTS adoptions (
 id SERIAL PRIMARY KEY, dog_id INTEGER NOT NULL UNIQUE REFERENCES dogs(id),
 applicant VARCHAR(120) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS seed_history (version INTEGER PRIMARY KEY);
INSERT INTO breeds (name) VALUES ('Метис'), ('Корги'), ('Лабрадор') ON CONFLICT DO NOTHING;
INSERT INTO shelters (name,city) VALUES ('Добрые лапы','Москва'), ('Хвост и дом','Казань') ON CONFLICT DO NOTHING;
INSERT INTO dogs (name,age,breed_id,shelter_id)
 SELECT v.name,v.age,b.id,s.id FROM (VALUES ('Бублик',2,'Корги'),('Луна',1,'Метис'),('Рэй',4,'Лабрадор')) AS v(name,age,breed)
 JOIN breeds b ON b.name=v.breed CROSS JOIN shelters s
 WHERE s.name='Добрые лапы' AND NOT EXISTS (SELECT 1 FROM seed_history WHERE version=1);
INSERT INTO seed_history VALUES (1) ON CONFLICT DO NOTHING;
