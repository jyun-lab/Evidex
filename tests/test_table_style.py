import unittest

from evidex.core.table_style import EVEN_ROW_TAG, ODD_ROW_TAG, stripe_tag


class TableStyleTests(unittest.TestCase):
    def test_stripe_tag_alternates_by_row_index(self):
        self.assertEqual(stripe_tag(0), ODD_ROW_TAG)
        self.assertEqual(stripe_tag(1), EVEN_ROW_TAG)
        self.assertEqual(stripe_tag(2), ODD_ROW_TAG)


if __name__ == "__main__":
    unittest.main()
