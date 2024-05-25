import asyncio
from JiraApi import JiraAPI


async def fetch_jira(jql: str, expand: str = "operations") -> list:
    jira = JiraAPI("jira_host", "jira_username", "jira_password")
    await jira.initialize()

    return await jira.select(jql, expand)


async def main() -> list:
    jql = "..."
    res = await fetch_jira(jql)
    return res


if __name__ == "__main__":
    asyncio.run(main())
