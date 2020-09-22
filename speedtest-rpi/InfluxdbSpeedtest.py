import os
import sys
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
import speedtest
import time

class configManager():

    def __init__(self):
        self._load_config_values()
        print('Configuration Successfully Loaded')

    def _load_config_values(self):

        # General
        self.delay = int(os.getenv('DELAY', '2'))
        self.output = 'True' == os.getenv('OUTPUT', 'True')

        # InfluxDB
        self.influx_address = os.getenv('INFLUXDB_HOST', 'influxdb')
        self.influx_port = int(os.getenv('INFLUXDB_PORT', '8086'))
        self.influx_database = os.getenv('INFLUXDB_DB', 'speedtests')
        self.influx_user = os.getenv('INFLUXDB_USER', '')
        self.influx_password = os.getenv('INFLUXDB_PASS', '')
        self.influx_ssl = 'True' == os.getenv('INFLUXDB_SSL', 'False')
        self.influx_verify_ssl = 'True' == os.getenv('INFLUXDB_VERIFY_SSL', 'True')

        # Speedtest
        test_server = os.getenv('SPEEDTEST_SERVER', None)
        if test_server:
            self.test_server.append(test_server)
        else:
            self.test_server = None


class InfluxdbSpeedtest():

    def __init__(self):

        self.config = configManager()
        self.output = self.config.output
        self.influx_client = InfluxDBClient(
            self.config.influx_address,
            self.config.influx_port,
            username=self.config.influx_user,
            password=self.config.influx_password,
            database=self.config.influx_database,
            ssl=self.config.influx_ssl,
            verify_ssl=self.config.influx_verify_ssl
        )

        self.speedtest = None
        self.results = None
        self.setup_speedtest()

    def setup_speedtest(self):

        speedtest.build_user_agent()

        print('Getting speedtest.net Configuration')
        try:
            self.speedtest = speedtest.Speedtest()
        except speedtest.ConfigRetrievalError:
            print('ERROR: Failed to get speedtest.net configuration.  Aborting')
            sys.exit(1)

        try:
            if self.config.test_server:
                self.speedtest.get_servers(self.config.test_server)
            else:
                self.speedtest.get_servers()
        except speedtest.NoMatchedServers:
            print('ERROR: No matched servers: {}'.format(self.config.test_server[0]))
            sys.exit(1)
        except speedtest.ServersRetrievalError:
            print('ERROR: Cannot retrieve speedtest server list')
            sys.exit(1)
        except speedtest.InvalidServerIDType:
            print('{} is an invalid server type, must be int'.format(self.config.test_server[0]))
            sys.exit(1)

        print('Picking the closest server')
        self.speedtest.get_best_server()

        self.results = self.speedtest.results

    def send_results(self):

        result_dict = self.results.dict()

        input_points = [
            {
                'measurement': 'speed_test_results',
                'fields': {
                    'download': result_dict['download'],
                    'upload': result_dict['upload'],
                    'ping': result_dict['server']['latency']
                },
                'tags': {
                    'server': result_dict['server']['sponsor']
                }
            }
        ]

        if self.output:
            print('Download: {}'.format(str(result_dict['download'])))
            print('Upload: {}'.format(str(result_dict['upload'])))

        self.write_influx_data(input_points)

    def run(self):

        while True:

            self.speedtest.download()
            self.speedtest.upload()

            self.send_results()

            time.sleep(self.config.delay)

    def write_influx_data(self, json_data):
        """
        Writes the provided JSON to the database
        :param json_data:
        :return:
        """
        if self.output:
            print(json_data)

        try:
            self.influx_client.write_points(json_data)
        except (InfluxDBClientError, ConnectionError, InfluxDBServerError) as e:
            if hasattr(e, 'code') and e.code == 404:

                print('Database {} Does Not Exist.  Attempting To Create'.format(self.config.influx_database))

                # TODO Grab exception here
                self.influx_client.create_database(self.config.influx_database)
                self.influx_client.write_points(json_data)

                return

            print('ERROR: Failed To Write To InfluxDB')
            print(e)

        if self.output:
            print('Written To Influx: {}'.format(json_data))


def main():

    collector = InfluxdbSpeedtest()
    collector.run()


if __name__ == '__main__':
    main()
