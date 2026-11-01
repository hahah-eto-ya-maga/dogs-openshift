import unittest
from unittest.mock import patch
from app import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_without_database(self):
        self.assertEqual(self.client.get('/healthz').json, {'status': 'ok'})

    def test_home_and_info(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertIn('pod', self.client.get('/api/info').json)

    def test_invalid_dogs_do_not_touch_database(self):
        valid = dict(name='Бублик', age=2, breed_id=1, shelter_id=1)
        with patch('app.database') as db:
            for key, value in [('name', ''), ('name', 'x' * 121), ('age', True),
                               ('age', -1), ('age', 31), ('breed_id', 0), ('shelter_id', '1')]:
                with self.subTest(key=key, value=value):
                    self.assertEqual(self.client.post('/api/dogs', json={**valid, key: value}).status_code, 400)
            db.assert_not_called()

    def test_invalid_json(self):
        for value in [[], 'dog', None]:
            self.assertEqual(self.client.post('/api/dogs', json=value).status_code, 400)

    def test_missing_applicant(self):
        self.assertEqual(self.client.post('/api/adoptions', json={'dog_id': 1}).status_code, 400)

    def test_unknown_route(self):
        self.assertEqual(self.client.get('/api/unknown').status_code, 404)

    def test_large_body(self):
        self.assertEqual(self.client.post('/api/dogs', json={'name': 'x' * 20000}).status_code, 413)
