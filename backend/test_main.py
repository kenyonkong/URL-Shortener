import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from backend import main


class UrlShortenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_database_path = main.DATABASE_PATH
        main.DATABASE_PATH = Path(self.temp_directory.name) / "test.db"
        main.initialize_database()
        self.request = SimpleNamespace(base_url="http://testserver/")

    def tearDown(self) -> None:
        main.DATABASE_PATH = self.original_database_path
        self.temp_directory.cleanup()

    def shorten(self, url: str) -> main.ShortenResponse:
        payload = main.ShortenRequest(url=url)
        return asyncio.run(main.shorten_url(payload, self.request))

    def test_different_urls_get_different_codes_and_same_url_is_reused(self) -> None:
        first = self.shorten("https://example.com/first")
        second = self.shorten("https://example.com/second")
        repeated = self.shorten("https://example.com/first")

        self.assertNotEqual(first.short_code, second.short_code)
        self.assertEqual(first.short_code, repeated.short_code)
        self.assertEqual(
            first.shortened_url, f"http://testserver/{first.short_code}"
        )

    def test_redirect_increments_access_count_and_data_persists(self) -> None:
        shortened = self.shorten("https://example.com/article")

        first_redirect = asyncio.run(main.redirect_short_url(shortened.short_code))
        second_redirect = asyncio.run(main.redirect_short_url(shortened.short_code))

        self.assertEqual(first_redirect.status_code, 307)
        self.assertEqual(first_redirect.headers["location"], "https://example.com/article")
        self.assertEqual(second_redirect.status_code, 307)

        # Running initialization again simulates a backend restart: the existing
        # table and rows must remain intact.
        main.initialize_database()
        with main.get_connection() as connection:
            row = connection.execute(
                "SELECT original_url, access_count FROM urls WHERE short_code = ?",
                (shortened.short_code,),
            ).fetchone()

        self.assertEqual(tuple(row), ("https://example.com/article", 2))

    def test_list_returns_all_url_pairs_newest_first(self) -> None:
        first = self.shorten("https://example.com/first")
        second = self.shorten("https://example.com/second")

        urls = asyncio.run(main.list_short_urls(self.request))

        self.assertEqual(
            [item.original_url for item in urls],
            ["https://example.com/second", "https://example.com/first"],
        )
        self.assertEqual(urls[0].shortened_url, second.shortened_url)
        self.assertEqual(urls[1].shortened_url, first.shortened_url)

    def test_resolve_returns_original_url_and_counts_visit(self) -> None:
        shortened = self.shorten("https://example.com/resolved")

        resolved = asyncio.run(main.resolve_short_url(shortened.short_code))

        self.assertEqual(resolved.original_url, "https://example.com/resolved")
        with main.get_connection() as connection:
            access_count = connection.execute(
                "SELECT access_count FROM urls WHERE short_code = ?",
                (shortened.short_code,),
            ).fetchone()["access_count"]
        self.assertEqual(access_count, 1)

    def test_redirect_is_rejected_after_visit_limit(self) -> None:
        shortened = self.shorten("https://example.com/limited")

        for _ in range(main.MAX_VISITS):
            response = asyncio.run(main.redirect_short_url(shortened.short_code))
            self.assertEqual(response.status_code, 307)

        with self.assertRaises(HTTPException) as error:
            asyncio.run(main.resolve_short_url(shortened.short_code))

        self.assertEqual(error.exception.status_code, 429)
        with main.get_connection() as connection:
            access_count = connection.execute(
                "SELECT access_count FROM urls WHERE short_code = ?",
                (shortened.short_code,),
            ).fetchone()["access_count"]
        self.assertEqual(access_count, main.MAX_VISITS)

    def test_unknown_short_code_returns_not_found(self) -> None:
        with self.assertRaises(HTTPException) as error:
            asyncio.run(main.resolve_short_url("missing"))

        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
