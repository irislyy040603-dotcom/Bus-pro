import unittest
from unittest.mock import patch
import app
from collector import extract_title


class DataTests(unittest.TestCase):
    def test_html_title(self):
        self.assertEqual(
            extract_title("<html><title>巴士報站</title></html>"), "巴士報站"
        )
        self.assertEqual(
            extract_title("<TITLE>\n Bus &amp; Stop </TITLE>"), "Bus & Stop"
        )
        with self.assertRaises(ValueError):
            extract_title("<html>no title</html>")

    def test_route_regex(self):
        self.assertEqual(
            app.parse_route_points("113.56,22.14;-113,0;"),
            [[22.14, 113.56], [0, -113]],
        )
        for value in ("113,", ",22", "113,22,7", "bad,22", "113,91", "nan,22"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                app.parse_route_points(value)

    def test_station_cache(self):
        payload = {"header": "000", "data": {"routeInfo": [{"staCode": "M800"}]}}
        with patch.object(app, "station_cache", {}), patch("app.fetch", return_value=payload) as fetch:
            app.get_stations("0")
            app.get_stations("0")
            self.assertEqual(fetch.call_count, 1)
            app.get_stations("1")
            self.assertEqual(fetch.call_count, 2)
            cached, stamp = app.station_cache["0"]
            app.station_cache["0"] = cached, stamp - app.STATION_TTL
            app.get_stations("0")
            self.assertEqual(fetch.call_count, 3)

    def test_speed(self):
        for value in (None, "", "unknown", -1, float("nan"), float("inf")):
            self.assertIsNone(app.normalize_speed(value))
        self.assertEqual(app.normalize_speed(0), 0)
        self.assertEqual(app.normalize_speed("22"), 22)

    def test_coordinates(self):
        self.assertEqual(
            app.coordinates({"latitude": "22.14", "longitude": "113.56"}),
            [22.14, 113.56],
        )
        with self.assertRaises(ValueError):
            app.coordinates({"latitude": "nan", "longitude": "113.56"})

    def test_cache_and_refresh(self):
        snapshot = dict(stops=[], vehicles=[], segments=[], vehicle_count=0, updated_at='test')
        states={d:dict(cache=None,last_attempt=None,error=None) for d in ('0','1')}
        with patch.object(app,'states',states):
            client=app.app.test_client()
            with patch('app.collect',return_value=snapshot) as collect:
                self.assertEqual(client.get('/api/route?direction=0').status_code,200)
                client.get('/api/route?direction=0&refresh=1')
                self.assertEqual(collect.call_count,1)
                states['0']['last_attempt']-=11
                client.get('/api/route?direction=0')
                self.assertEqual(collect.call_count,2)
                client.get('/api/route?direction=1')
                self.assertEqual(collect.call_count,3)
                collect.assert_called_with('1')
            with patch('app.collect',side_effect=ValueError('outage')), patch.object(app.app.logger,'exception'):
                states['0']['last_attempt']=None
                response=client.get('/api/route?direction=0')
                self.assertTrue(response.json['stale'])
                self.assertEqual(response.status_code,200)
                states['1']=dict(cache=None,last_attempt=None,error=None)
                self.assertEqual(client.get('/api/route?direction=1').status_code,503)
            self.assertEqual(client.get('/api/route?direction=2').status_code,400)


if __name__ == "__main__":
    unittest.main()
