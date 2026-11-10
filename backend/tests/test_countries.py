import unittest

from core.countries import COUNTRIES, NOT_APPLICABLE, validate_countries


class ValidateCountriesTest(unittest.TestCase):
    def test_accepts_countries_and_dedupes(self):
        self.assertEqual(validate_countries(['India', 'Bangladesh', 'India']), ['India', 'Bangladesh'])

    def test_accepts_na_alone(self):
        self.assertEqual(validate_countries([NOT_APPLICABLE]), [NOT_APPLICABLE])

    def test_rejects_empty_unknown_and_na_with_country(self):
        for bad in ([], ['Atlantis'], [NOT_APPLICABLE, 'India']):
            with self.assertRaises(ValueError):
                validate_countries(bad)

    def test_list_has_no_duplicates(self):
        self.assertEqual(len(COUNTRIES), len(set(COUNTRIES)))


if __name__ == '__main__':
    unittest.main()
