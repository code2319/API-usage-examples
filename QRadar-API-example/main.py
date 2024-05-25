#!/usr/bin/env python3
import os
import sys
import time
import hvac
import datetime
from typing import Tuple
from RestApiClient import RestApiClient


def vault_role_and_sescret() -> Tuple[str, str]:
    if os.name == "nt":
        return os.getenv('role_id'), os.getenv('secret_id')
    else:
        return os.environ.get('role_id'), os.environ.get('secret_id')


def vault_data() -> dict:
    role_id, secret_id = vault_role_and_sescret()
    
    client = hvac.Client(url="vault.url")
    client.auth.approle.login(
        role_id=role_id,
        secret_id=secret_id
    )

    if client.is_authenticated():
        data = client.secrets.kv2.read_secret(
            path="path",
            mount_point="moint_point"
        )['data']['data']

        return data
    else:
        sys.stderr.write("No vault connection\n")


def download_report(query: str):
    report_name = "test_report.csv"

    progress, query_execution_time, status, search_id = rest.create_search(query_expression=query)

    sys.stdout.write("While search status != 'COMPLETED' - every 5 minutes check its status:\n")
    while status != "COMPLETED":
        progress, query_execution_time, status = rest.check_status(search_id)
        sys.stdout.write(
            f"\t{str(datetime.datetime.now().strftime('%H:%M:%S'))} - {search_id} - {status} - {progress}%\n")
        time.sleep(5 * 60)

    sys.stdout.write(f"\tQuery execution time - {query_execution_time / 60000} min.\n")

    sys.stdout.write("\n ")
    sys.stdout.write("save_results = True\nThis ensures that the search is not automatically "
                     "removed when it expires in accordance with the retention policy.\n")
    rest.save_search(search_id)

    sys.stdout.write("Saving request data to a .csv file.\n")
    rest.save_to_file(search_id, report_name)


if __name__ == "__main__":
    main_file_path = os.path.dirname(os.path.abspath(__file__))
    data = vault_data()

    aql_query = "example query"
    rest = RestApiClient('14.0', data['qradar_ip'], data['qradar_token'], main_file_path)

    if rest.verify_config():
        sys.stdout.write("QRadar configuration alidation successfull!\n")

        download_report(aql_query)
    else:
        sys.stderr.write("QRadar configuration alidation unsuccessfull!\n")
