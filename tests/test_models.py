import unittest
from pydantic import ValidationError
from app.models.link import LinkCreate, LinkResponse, PopularLink, DashboardData


class TestLinkModels(unittest.TestCase):
    def test_valid_link_create(self):
        data = LinkCreate(
            target_url="https://example.com/test",
            title="Example Title",
            custom_slug="my-custom-slug",
        )
        self.assertEqual(str(data.target_url), "https://example.com/test")
        self.assertEqual(data.title, "Example Title")
        self.assertEqual(data.custom_slug, "my-custom-slug")

    def test_invalid_target_url(self):
        with self.assertRaises(ValidationError):
            LinkCreate(target_url="not-a-valid-url")

    def test_invalid_custom_slug_characters(self):
        with self.assertRaises(ValidationError):
            LinkCreate(target_url="https://example.com", custom_slug="invalid slug with spaces!")

    def test_reserved_custom_slug(self):
        with self.assertRaises(ValidationError):
            LinkCreate(target_url="https://example.com", custom_slug="docs")

    def test_slug_trimmed_and_lowercased(self):
        data = LinkCreate(target_url="https://example.com", custom_slug="  MySlug123  ")
        self.assertEqual(data.custom_slug, "myslug123")

    def test_slug_url_normalization(self):
        data1 = LinkCreate(target_url="https://example.com", custom_slug="http://youyou")
        self.assertEqual(data1.custom_slug, "youyou")

        data2 = LinkCreate(target_url="https://example.com", custom_slug="http://localhost:8000/r/my-link")
        self.assertEqual(data2.custom_slug, "my-link")

        data3 = LinkCreate(target_url="https://example.com", custom_slug="/r/another-link")
        self.assertEqual(data3.custom_slug, "another-link")


if __name__ == "__main__":
    unittest.main()
