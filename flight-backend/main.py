import os
import json
import io
import uuid
import datetime
import boto3
import psycopg2
import requests

# Настройки берём из переменных окружения
PG_HOST = os.environ.get('PG_HOST')
PG_PORT = int(os.environ.get('PG_PORT', 6432))
PG_DB = os.environ.get('PG_DB')
PG_USER = os.environ.get('PG_USER')
PG_PASSWORD = os.environ.get('PG_PASSWORD')
S3_ENDPOINT_URL = os.environ.get('S3_ENDPOINT_URL')

S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY')
BUCKET = os.environ.get('BUCKET_NAME', 'tickets-bucket')
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', 'https://storage.yandexcloud.net')

SMARTCAPTCHA_SECRET = os.environ.get('SMARTCAPTCHA_SECRET')  # или другой метод
SMARTCAPTCHA_VERIFY_URL = os.environ.get('SMARTCAPTCHA_VERIFY_URL', 'https://smartcaptcha.api.cloud.yandex.net/v1/captcha:verify')

# Инициализация S3 клиент
s3 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY
)

def get_db_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD, sslmode="require"
    )

# Функция-обработчик HTTP (Cloud Functions)
def handler(event, context):
    # Логируем всё событие, чтобы видеть httpMethod, path и headers
    print("=== Incoming Event ===")
    print(json.dumps(event, indent=2, ensure_ascii=False))
    print("=====================")
    
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }

    # Preflight request
    if event.get('httpMethod') == 'OPTIONS':
        print("Received preflight OPTIONS request")
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    method = event.get('httpMethod')
    path = event.get('path') or '/'
    # простая маршрутизация
    if method == 'GET' and path == '/flights':
        return get_flights()
    if method == 'POST' and path == '/buy':
        body = json.loads(event.get('body') or '{}')
        return buy_ticket(body)
    if method == 'GET' and path.startswith('/ticket/'):
        ticket_id = path.split('/')[-1]
        return get_ticket(ticket_id)
    return respond(404, {'error':'not found'})

def get_flights():
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, number, departure, arrival, price FROM flights ORDER BY id")
        rows = cur.fetchall()
        #flights = [{'id':r[0],'number':r[1],'departure':r[2],'arrival':r[3],'price':float(r[4])} for r in rows]
        flights = [{
            'id': r[0],
            'number': r[1],
            'departure': r[2].isoformat() if isinstance(r[2], datetime.datetime) else r[2],
            'arrival': r[3].isoformat() if isinstance(r[3], datetime.datetime) else r[3],
            'price': float(r[4])
        } for r in rows]

        cur.close()
        conn.close()
        return respond(200, flights)
    except Exception as e:
        return respond(500, {'error': str(e)})

def verify_captcha(token):
    # Простейший пример вызова SmartCaptcha API; читать официальную документацию для точных полей/формата.
    payload = {'token': token, 'secret': SMARTCAPTCHA_SECRET}
    r = requests.post(SMARTCAPTCHA_VERIFY_URL, json=payload, timeout=5)
    return r.status_code == 200 and r.json().get('success', False)

def buy_ticket(body):
    flight_id = body.get('flight_id')
    passenger_name = body.get('passenger_name')
    email = body.get('email')
    captcha_token = body.get('captcha_token')

    if not all([flight_id, passenger_name, email, captcha_token]):
        return respond(400, {'error':'missing fields'})

    # верификация капчи
    #ok = verify_captcha(captcha_token)
    ok = True
    if not ok:
        return respond(403, {'error':'captcha_failed'})

    try:
        conn = get_db_conn()
        cur = conn.cursor()
        # вставляем запись в tickets
        cur.execute(
            "INSERT INTO tickets(flight_id, passenger_name, email, ticket_url) VALUES (%s,%s,%s,%s) RETURNING id",
            (flight_id, passenger_name, email, '')
        )
        ticket_id = cur.fetchone()[0]
        conn.commit()

        # генерируем текстовый билет
        cur.execute("SELECT number, departure, arrival, price FROM flights WHERE id=%s", (flight_id,))
        fl = cur.fetchone()
        ticket_text = f"Билет ID: {ticket_id}\nПассажир: {passenger_name}\nE-mail: {email}\nРейс: {fl[0]} {fl[1]} → {fl[2]}\nСтоимость: {fl[3]} ₽\nДата покупки: {datetime.datetime.utcnow().isoformat()}Z\n"
        filename = f"ticket_{ticket_id}.txt"
        s3.put_object(Bucket=BUCKET, Key=filename, Body=ticket_text.encode('utf-8'))

        # формируем публичный URL (если бакет публичный) или временную ссылку
        ticket_url = f"{S3_ENDPOINT_URL}/{BUCKET}/{filename}"

        # обновляем запись tickets
        cur.execute("UPDATE tickets SET ticket_url=%s WHERE id=%s", (ticket_url, ticket_id))
        conn.commit()
        cur.close()
        conn.close()

        return respond(200, {'ticket_id': ticket_id, 'ticket_url': ticket_url})
    except Exception as e:
        return respond(500, {'error': str(e)})

def get_ticket(ticket_id):
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT ticket_url FROM tickets WHERE id=%s", (ticket_id,))
        r = cur.fetchone()
        cur.close()
        conn.close()
        if not r:
            return respond(404, {'error':'ticket_not_found'})
        return respond(200, {'ticket_url': r[0]})
    except Exception as e:
        return respond(500, {'error': str(e)})

def respond(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',  # для демонстрации; в prod ограничьте
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body)
    }
