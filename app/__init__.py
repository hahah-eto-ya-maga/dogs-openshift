import os
import socket
from contextlib import contextmanager
from pathlib import Path

import pg8000.dbapi
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16384

@contextmanager
def database():
    conn = pg8000.dbapi.connect(
        host=os.getenv('DB_HOST', 'db'), port=int(os.getenv('DB_PORT', '5432')),
        database=os.getenv('DB_NAME', 'dogs'), user=os.getenv('DB_USER', 'dogs'),
        password=os.environ['DB_PASSWORD'], timeout=5,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def query(conn, sql, args=()):
    cur = conn.cursor()
    cur.execute(sql, args)
    if cur.description:
        names = [c[0] for c in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]
    return []

def initialize():
    with database() as conn:
        query(conn, 'SELECT pg_advisory_xact_lock(731894)')
        for statement in Path(__file__).with_name('schema.sql').read_text().split(';'):
            if statement.strip():
                query(conn, statement)

@app.get('/')
def index():
    return render_template('index.html')

@app.get('/healthz')
def health():
    return {'status': 'ok'}

@app.get('/readyz')
def ready():
    with database() as conn:
        query(conn, 'SELECT id FROM dogs LIMIT 1')
    return {'status': 'ready'}

@app.get('/api/info')
def info():
    return {'pod': socket.gethostname(), 'version': os.getenv('APP_VERSION', '1.0'),
            'message': os.getenv('WELCOME_MESSAGE', 'Каждой собаке нужен дом')}

@app.get('/api/breeds')
@app.get('/api/shelters')
@app.get('/api/dogs')
@app.get('/api/adoptions')
def list_entities():
    table = request.path.rsplit('/', 1)[-1]
    with database() as conn:
        return jsonify(query(conn, f'SELECT * FROM {table} ORDER BY id'))

def payload(fields):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('Нужен JSON-объект')
    out = {}
    for name, kind in fields.items():
        value = data.get(name)
        if kind is int:
            if type(value) is not int or value < (0 if name == 'age' else 1) or value > 1000000:
                raise ValueError(f'{name}: требуется допустимое целое число')
            if name == 'age' and value > 30:
                raise ValueError('Возраст должен быть от 0 до 30')
        elif not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
            raise ValueError(f'{name}: требуется строка от 1 до 120 символов')
        out[name] = value.strip() if isinstance(value, str) else value
    return out

@app.post('/api/breeds')
@app.post('/api/shelters')
def create_reference():
    table = request.path.rsplit('/', 1)[-1]
    fields = {'name': str} if table == 'breeds' else {'name': str, 'city': str}
    data = payload(fields)
    with database() as conn:
        row = query(conn, f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join(['%s'] * len(fields))}) RETURNING *", tuple(data.values()))[0]
    return row, 201

@app.post('/api/dogs')
def create_dog():
    data = payload({'name': str, 'age': int, 'breed_id': int, 'shelter_id': int})
    with database() as conn:
        row = query(conn, 'INSERT INTO dogs (name,age,breed_id,shelter_id) VALUES (%s,%s,%s,%s) RETURNING *', tuple(data.values()))[0]
    return row, 201

@app.post('/api/adoptions')
def adopt():
    data = payload({'dog_id': int, 'applicant': str})
    with database() as conn:
        dog = query(conn, 'SELECT * FROM dogs WHERE id=%s FOR UPDATE', (data['dog_id'],))
        if not dog:
            return {'error': 'Собака не найдена'}, 404
        if dog[0]['status'] != 'available':
            return {'error': 'Собака уже нашла дом'}, 409
        row = query(conn, 'INSERT INTO adoptions (dog_id,applicant) VALUES (%s,%s) RETURNING *', tuple(data.values()))[0]
        query(conn, "UPDATE dogs SET status='adopted' WHERE id=%s", (data['dog_id'],))
    return row, 201

@app.delete('/api/dogs/<int:dog_id>')
def delete_dog(dog_id):
    with database() as conn:
        rows = query(conn, 'DELETE FROM dogs WHERE id=%s RETURNING id', (dog_id,))
    return ('', 204) if rows else ({'error': 'Собака не найдена'}, 404)

@app.errorhandler(ValueError)
def invalid(exc):
    return {'error': str(exc)}, 400

@app.errorhandler(pg8000.dbapi.DatabaseError)
def db_error(exc):
    details = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {}
    if details.get('C') in ('23503', '23505', '23514'):
        return {'error': 'Нарушена связь, уникальность или ограничение данных'}, 409
    app.logger.exception('Database failure')
    return {'error': 'База данных недоступна или не инициализирована'}, 503

@app.errorhandler(pg8000.dbapi.InterfaceError)
def connection_error(exc):
    app.logger.error('Database connection failed: %s', type(exc).__name__)
    return {'error': 'База данных недоступна'}, 503

@app.errorhandler(HTTPException)
def http_error(exc):
    return {'error': exc.description}, exc.code
