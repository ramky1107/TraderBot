import unittest

from news import build_market_news_url, derive_outlook_from_news


class GrowwNewsTests(unittest.TestCase):
    def test_build_market_news_url_appends_market_news_suffix(self):
        url = build_market_news_url('https://groww.in/stocks/share-india-securities-ltd')
        self.assertEqual(url, 'https://groww.in/stocks/share-india-securities-ltd/market-news')

    def test_derive_outlook_from_news_marks_bullish_keywords(self):
        result = derive_outlook_from_news(
            company='Share India',
            title='Share India Q1 Profit Jumps 47% YoY',
            body='The company reported a strong YoY rebound in profitability during Q1.',
            page_excerpt='Order wins and strong earnings support the stock outlook.',
        )

        self.assertEqual(result['sentiment'], 'bullish')
        self.assertIn('bullish', result['summary'].lower())
        self.assertIn('breakout', result['day_trade_plan'].lower())


if __name__ == '__main__':
    unittest.main()
