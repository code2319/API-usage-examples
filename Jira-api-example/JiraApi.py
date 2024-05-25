#!/usr/bin/python
# -*- coding: utf-8 -*-

import ssl
import sys
import base64
import urllib
import asyncio
import urllib.parse
import aiohttp
import aiohttp_retry
from loguru import logger


class JiraAPI:
    def __init__(
        self,
        jira_host: str,
        jira_username: str,
        jira_password: str,
        attempts: int = 3,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize Jira API.

        Args:
            host (str): The base URL of the Jira instance.
            username (str): The username for authentication.
            password (str): The password for authentication.
            max_tries (int): Maximum number of retry attemps for HTTP requests.
            debug (bool): Enable debug mode.

        Returns:
            None
        """
        self.jira_host = jira_host
        self.jira_username = jira_username
        self.jira_password = jira_password
        self.attempts = attempts
        self.timeout = timeout
        self.max_results = 20

        self.ssl_context = ssl.SSLContext()
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.retry_options = {
            "attempts": self.attempts,
            "max_timeout": self.timeout,
            "statuses": (500, 502, 503, 504),
            "exceptions": aiohttp.ClientError,
        }

    async def initialize(self) -> None:
        """
        Initialize the Jira API instance.

        Attempts to authenticate using provided credentials.

        Raises:
            SystemExit: If authentication fails.

        Returns:
            None
        """
        if not await self.authenticate():
            sys.exit("Authentication failed. Please check your credentials.")

    async def authenticate(self) -> bool:
        """
        Authenticate with the Jira API.

        Attempts to authenticate using provided credentials.

        Returtns:
            bool: True if authentication is successful, False otherwise
        """
        if not self.jira_username or self.jira_password:
            logger.error("Username or password not provided")
            return False

        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=self.ssl_context)
            ) as session:
                async with aiohttp_retry.RetryClient(
                    session, **self.retry_options
                ) as retry_client:
                    response = await self.request(session=retry_client)

                    if 200 <= response.status < 300:
                        logger.success(f"Authentication successful: {response.status}")
                        return True
                    else:
                        logger.error(
                            f"Authentication failed: {response.status} - {response.reason}"
                        )
                        return False
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False

    def get_auth_header(self) -> str:
        """
        Get the authentication header for requests.

        Returns:
            str: The authentication header.
        """
        user_pass = f"{self.jira_username}:{self.jira_password}".encode()
        base64string = base64.b64decode(user_pass).decode()
        return base64string

    async def request(
        self,
        session: aiohttp.ClientSession,
        pattern: str = "mypermissions",
        data: dict = None,
        headers: dict = None,
        method: str = "GET",
        params: dict = None,
    ) -> aiohttp.ClientResponse:
        """
        Make an HTTP request to the Jira API.

        Args:
            session (ClientSession): The aiohttp session object.
            pattern (str, optional): The API endpoint pattern. Defaults to "mypermissions".
            data (dict, optional): The request body data. Defaults to None.
            headers (dict, optional): The request headers. Defaults to None.
            method (str, optional): The HTTP method. Defaults to "GET".
            params (dict, optional): The query parameters. Defaults to None.

        Returns:
            ClientResponse: The aiohttp response object.

        Raises:
            ClientResponseError: If the requests encounters an error.
        """
        if headers is None:
            headers = {}
        if params is None:
            params = {}

        url = f"{self.jira_host}/rest/api/2/{pattern}"
        logger.info(f"URL: {url}")

        headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Basic: {self.get_auth_header()}"

        async with session.requests(method, url, params, headers, data) as response:
            return await self.handle_response(response)

    async def handle_response(self, response) -> dict:
        """
        Handle the responsse from an HTTP request.

        Args:
            response (ClientResponse): The aiohttp response object.

        Returns:
            dict: The response data.
        """
        error = {"Result": None, "Raw_text": None}

        if response is None:
            logger.error("No response received.")
            return error

        try:
            response.raise_for_status()
            error["Result"] = response.status
            error["Raw_text"] = await response.text()

            try:
                error = await response.json()
            except:
                pass

        except aiohttp.ClientResponseError as e:
            if response.status == 404:
                logger.error(f"Resource not found {response.request_info.real_url}")
            else:
                logger.error(
                    f"Error during request: {e.status}, message='{response.reason}'"
                )
                logger.error(f"Status code: {response.status if response else 'N/A'}")
                try:
                    logger.error(await e.text())
                except:
                    pass
            sys.exit(1)

        return response

    async def select(
        self, jql: str = None, expand: str = "changelog", fields: str = "*all"
    ) -> list:
        """
        Select data from the Jira API based on a JQL query.

        Args:
            jql (str, required): The JQL query. Defaults to None.
            expand (str, optional): The fields to expand. Defaults to "changelog".
            fields (str, optional): The fields to retrieve. Defaults to "*all".


        Returns:
            list: A list of data objects.
        """
        if jql is None or jql == "":
            logger.error("JQL query is not provided.")
            sys.exit(1)

        pattern = f"search?jql={urllib.parse.quote(jql, safe='/?:=,&')}&maxResults={self.max_results}&expand={expand}&fields={fields}"

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=self.ssl_context)
        ) as session:
            async with aiohttp_retry.RetryClient(
                session, **self.retry_options
            ) as retry_client:
                response = await self.request(retry_client, pattern)

                if response.status == 200:
                    data = await response.json()

                    issues = data.get("total", 0)
                    logger.info(f"Found {issues} issues.")

                    tasks = [
                        self.fetch(session, pattern, start)
                        for start in range(0, issues, self.max_results)
                    ]

                    results = await asyncio.gather(*tasks)

                return results

    async def fetch(
        self, session: aiohttp.ClientSession, pattern: str, start: int
    ) -> list:
        """
        Fetch data from the Jira API.

        Args:
            session (ClientSession): The aiohttp session object.
            pattern (str): The API endpoind pattern.
            start (int): The starting index for fetching data.

        Returns:
            list: A list of data objects.
        """
        logger.debug(
            f"Fetching data from {self.jira_host}/rest/api/2/{pattern}/&startAt={start}..."
        )

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {self.get_auth_header()}",
            }
            params = {"startAt": start}
            url = f"{self.jira_host}/rest/api/2/{pattern}"

            async with session.request(
                method="GET",
                url=url,
                headers=headers,
                params=params,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetchind data from {url}: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching data from {url}, reason: {str(e)}")
            return []
