"""Run against a running demo. Creates a dog and adoption, which remain visible."""
import concurrent.futures
import json
import os
import urllib.error
import urllib.request
import uuid

BASE = os.getenv('BASE_URL', 'http://localhost:8080').rstrip('/')

def call(path, method='GET', body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        content = response.read()
        return response.status, json.loads(content) if content else None

def check(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)

check(call('/readyz')[0] == 200, 'readiness')
status, breeds = call('/api/breeds')
check(status == 200 and breeds, 'breeds exist')
status, shelters = call('/api/shelters')
check(status == 200 and shelters, 'shelters exist')
status, dog = call('/api/dogs', 'POST', {'name': 'Тест-' + uuid.uuid4().hex[:8], 'age': 2,
                                      'breed_id': breeds[0]['id'], 'shelter_id': shelters[0]['id']})
check(status == 201, 'create dog')
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(lambda name: call('/api/adoptions', 'POST', {'dog_id': dog['id'], 'applicant': name}), ['Тест А', 'Тест Б']))
check(sorted(s for s, _ in results) == [201, 409], 'only one concurrent adoption succeeds')
check(call('/api/dogs/' + str(dog['id']), 'DELETE')[0] == 409, 'adoption protects dog from deletion')
status, dogs = call('/api/dogs')
check(status == 200 and next(d for d in dogs if d['id'] == dog['id'])['status'] == 'adopted', 'status persisted')
print('OK: readiness, creation, concurrent adoption, relationships, persistence. Demo dog id:', dog['id'])
