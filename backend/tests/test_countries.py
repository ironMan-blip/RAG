import unittest

from core.countries import COUNTRIES, GLOBAL, validate_country


class ValidateCountryTest(unittest.TestCase):
    def test_accepts_a_country_or_na(self):
        self.assertEqual(validate_country('India'), 'India')
        self.assertEqual(validate_country(GLOBAL), GLOBAL)

    def test_rejects_missing_and_unknown(self):
        for bad in (None, '', 'Atlantis'):
            with self.assertRaises(ValueError):
                validate_country(bad)

    def test_list_has_no_duplicates(self):
        self.assertEqual(len(COUNTRIES), len(set(COUNTRIES)))


if __name__ == '__main__':
    unittest.main()
