import os
import csv
import sys
import time
import datetime
import requests
from typing import Tuple


class RestApiClient:
    def __init__(self, api_version, qradar_ip, qradar_token, report_dir):
        self.api_version = api_version
        self.report_dir = report_dir
        self.config_section = 'DEFAULT'
        self.headers = {'Accept': 'application/json', 'Version': self.api_version, 'SEC': qradar_token}
        self.server_ip = f'https://{qradar_ip}'

    # params is for GET-style URL parameters, data is for POST-style body information
    def call_api(self, endpoint: str, **kwargs) -> requests.models.Response:
        try:
            r = requests.request(url=self.server_ip + endpoint,
                                 verify=False,
                                 **kwargs)
            if r is not None:
                return r
        except requests.exceptions.RequestException as e:
            sys.stderr.write(str(e) + "\n")

    def verify_config(self) -> bool:
        """
        Description
        -----------
        Retrieves a single version documentation object.

        Response Description
        --------------------
        A version documentation object.

        :return: bool
        """
        r = self.call_api(method="GET",
                          endpoint=f'/help/versions/{self.api_version}',
                          headers=self.headers)
        if r.status_code == 200:
            return True
        else:
            try:
                sys.stderr.write(f"{r.status_code} - {r.json()['description']}\n")
                sys.stderr.write(str(r.json()) + "\n")
            except (ValueError, KeyError):
                sys.stderr.write(str(r.text) + "\n")

    def create_search(self, query_expression: str) -> Tuple[int, int, str, str]:
        """
        Description
        -----------
        Creates a new Ariel search as specified by the Ariel Query Language (AQL) query expression.
        Searches are executed asynchronously. A reference to the search ID is returned and should be used in
        subsequent API calls to determine the status of the search and retrieve the results once it is complete.

        This endpoint only accepts SELECT query expressions.

        Queries are applied to the range of data in a certain time interval.
        By default this time interval is the last 60 seconds.
        An alternative time interval can be specified by specifying them as part of the query expression.
        For further information, see the AQL reference guide.

        Response Description
        --------------------
        Information about the specified search, including the search ID.
        Use the search ID to access or manipulate the search with the other API endpoints.

        If the exact search being created was already recently created, the response message
        will return a reference to the original search ID rather than creating a new search.

        :param query_expression: AQL query string
        :return: progress, query_execution_time, save_results, status, search_id
        """
        r = self.call_api(method="POST",
                          endpoint='/api/ariel/searches',
                          headers=self.headers,
                          data={'query_expression': query_expression})
        # 201 - success
        if r.status_code == 201:
            sys.stdout.write("\n ")
            sys.stdout.write(f"{r.status_code} - A new Ariel search was successfully created.\n")
            return r.json()['progress'], r.json()['query_execution_time'], r.json()['status'], r.json()['search_id']
        else:
            try:
                sys.stderr.write(f"{r.status_code} - {r.json()['description']}\n")
                sys.stderr.write(str(r.json()) + "\n")
            except (ValueError, KeyError):
                sys.stderr.write(str(r.text) + "\n")

    def check_status(self, search_id: str) -> Tuple[int, int, str]:
        """
        Description
        -----------
        Retrieve status information for a search, based on the search ID parameter.
        The same informational fields are returned regardless of whether the search is in progress or is complete.

        Response Description
        --------------------
        Information about the specified search, including the search status.

        :param search_id: str
        :return: progress: int, query_execution_time: int, save_results: bool, status: str
        """
        r = self.call_api(method="GET",
                          endpoint=f'/api/ariel/searches/{search_id}',
                          headers=self.headers)
        if r.status_code == 200 or r.status_code == 206:
            return r.json()['progress'], r.json()['query_execution_time'], r.json()['status']
        else:
            try:
                sys.stderr.write(f"{r.status_code} - {r.json()['description']}\n")
                sys.stderr.write(str(r.json()) + "\n")
            except (ValueError, KeyError):
                sys.stderr.write(str(r.text) + "\n")

    def save_search(self, search_id: str):
        """
        Description
        -----------
        Updates details for an Ariel search. You can update searches in the following ways:

        To cancel an active search, set the status parameter to CANCELED.
        This stops the search and keeps any search results that were collected before the search was canceled.
        The results for a completed search can be saved by setting the save_results parameter to true.
        This ensures that the search is not automatically removed when it expires in accordance with the retention policy.
        The Ariel server uses an internal retention policy to manage available disk space.
        Searches might be deleted automatically, according to the settings of the retention policy.
        Searches with saved results are not automatically reclaimed by the server and are therefore retained.
        A search can be explicitly deleted by using the DELETE /searches/{search_id} endpoint.

        Note: Saving too many search results might result in insufficient disk space to process new searches.

        Response Description
        --------------------
        Information about the specified search that was updated.

        :param search_id: str
        :return: status: str
        """
        headers = self.headers.copy()
        headers['search_id'] = search_id
        r = self.call_api(method="POST",
                          endpoint=f'/api/ariel/searches/{search_id}',
                          headers=headers,
                          data={"save_results": "True"})

        if r.status_code == 200:
            sys.stdout.write(str(f"{r.status_code} - The search was updated.\n"))
        else:
            try:
                sys.stderr.write(f"{r.status_code} - {r.json()['description']}\n")
                sys.stderr.write(str(r.json()) + "\n")
            except (ValueError, KeyError):
                sys.stderr.write(str(r.text) + "\n")

    def save_to_file(self, search_id: str, filename: str):
        """
        Description
        -----------
        Retrieve the results of the Ariel search that is identified by the search ID.
        The Accepts request header indicates the format of the result.
        The formats are RFC compliant and can be JSON, CSV, XML, or tabular text.

        By default, all query result records are returned.
        To restrict the results to a contiguous subset of the records, you can supply a
        Range header to specify the inclusive range of records to be returned.

        This end-point works with query results that are generated by AQL query expressions.
        This endpoint might not work as expected for results that are generated by other means.
        Search results might not be retrievable for searches that are created on the Console.

        The response samples are for the following query: Select sourceIP, destinationIP from events.

        Response Description
        --------------------
        The search results for the specified search ID.
        The format that is used to encapsulate the data depends on the format specified in the Accept header for this request.

        :param search_id: str
        :param filename: the name of the .csv-file where the qRadar data will be saved
        :return: nothing
        """
        headers = self.headers.copy()
        headers["Accept"] = 'application/csv'

        r = self.call_api(method="GET",
                          headers=headers,
                          endpoint=f'/api/ariel/searches/{search_id}/results',
                          stream=True)

        if r.status_code == 200:
            sys.stdout.write(str(f"{r.status_code} - The search results were retrieved.\n"))
            maxInt = sys.maxsize
            while True:
                # decrease the maxInt value by factor 10
                # as long as the OverflowError occurs.

                try:
                    csv.field_size_limit(maxInt)
                    break
                except OverflowError:
                    maxInt = int(maxInt / 10)

            decoded_content = r.content.decode('utf-8')
            decoded_content = decoded_content.replace("\"", "")

            with open(os.path.join(self.report_dir, filename), "w", encoding="utf8", newline="") as csv_file:
                writer_csv = csv.writer(csv_file)
                cr = csv.reader(decoded_content.splitlines())
                writer_csv.writerows(cr)

            fsize = self.humanize_bytes(os.stat(os.path.join(self.report_dir, filename)).st_size)
            sys.stdout.write(f"{filename} = {fsize}.\n")
        else:
            try:
                sys.stderr.write(f"{r.status_code} - {r.json()['description']}\n")
                sys.stderr.write(str(r.json()) + "\n")
            except (ValueError, KeyError):
                sys.stderr.write(str(r.text) + "\n")

    def humanize_bytes(self, bytes: int, precision: int = 1) -> str:
        """
        :returns: str
        """
        abbrevs = (
            (1 << 50, 'PB'),
            (1 << 40, 'TB'),
            (1 << 30, 'GB'),
            (1 << 20, 'MB'),
            (1 << 10, 'kB'),
            (1, 'bytes')
        )
        if bytes == 1:
            return '1 byte'
        for factor, suffix in abbrevs:
            if bytes >= factor:
                break

        return '%.*f %s' % (precision, bytes / factor, suffix)
