import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("PG_DSN", "postgresql://localhost/test")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

import main


class GuestbookTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    @patch("main.mongo_collection")
    @patch("main.psycopg.connect")
    def test_saves_optional_rating_to_both_databases(self, connect, collection):
        conn = connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = (42,)
        collection.insert_one.return_value.inserted_id = "mongo-id"

        result = main.save_submission(main.Submission(name="Camille", message="Bonjour", rating=5))

        self.assertEqual(result, {"postgres_id": 42, "mongo_id": "mongo-id"})
        self.assertEqual(conn.execute.call_args.args[1][:3], ("Camille", "", "Bonjour"))
        self.assertEqual(conn.execute.call_args.args[1][-1], 5)
        document = collection.insert_one.call_args.args[0]
        self.assertEqual((document["name"], document["rating"], document["pg_id"]), ("Camille", 5, 42))

    @patch("main.save_submission")
    def test_form_accepts_optional_rating_and_no_email(self, save):
        for data in (
            {"name": "Camille", "message": "Bonjour"},
            {"name": "Camille", "message": "Bonjour", "rating": "5"},
        ):
            response = self.client.post("/submit", data=data, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
        self.assertIsNone(save.call_args_list[0].args[0].rating)
        self.assertEqual(save.call_args_list[1].args[0].rating, 5)
        self.assertIsNone(save.call_args_list[1].args[0].email)

    @patch("main.save_submission")
    def test_invalid_ratings_are_rejected_and_old_api_payload_still_works(self, save):
        for rating in (0, 6):
            response = self.client.post(
                "/api/submissions", json={"name": "Camille", "message": "Bonjour", "rating": rating}
            )
            self.assertEqual(response.status_code, 422)
        save.assert_not_called()
        save.return_value = {"postgres_id": 1, "mongo_id": "id"}
        response = self.client.post(
            "/api/submissions",
            json={"name": "Camille", "email": "camille@example.com", "message": "Bonjour"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(save.call_args.args[0].email, "camille@example.com")

    @patch("main.list_mongo", return_value=[])
    @patch("main.list_postgres")
    def test_old_messages_render_without_rating_and_are_escaped(self, list_postgres, list_mongo):
        list_postgres.return_value = [{
            "id": 1,
            "name": "Camille",
            "email": "camille@example.com",
            "message": "<script>alert(1)</script>",
            "rating": None,
            "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        }]
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Camille", response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertNotIn("camille@example.com", response.text)
        self.assertNotIn("sur 5 étoiles", response.text)

        list_postgres.return_value[0]["rating"] = 4
        response = self.client.get("/")
        self.assertIn('aria-label="4 sur 5 étoiles"', response.text)
        self.assertIn("★★★★☆", response.text)


class SchemaTests(unittest.IsolatedAsyncioTestCase):
    @patch("main.mongo_client")
    @patch("main.psycopg.connect")
    async def test_startup_adds_rating_without_replacing_existing_table(self, connect, mongo_client):
        async with main.lifespan(main.app):
            conn = connect.return_value.__enter__.return_value
            statements = [call.args[0] for call in conn.execute.call_args_list]
            self.assertTrue(any("CREATE TABLE IF NOT EXISTS submissions" in sql for sql in statements))
            self.assertIn("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS rating INTEGER", statements)
        mongo_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
