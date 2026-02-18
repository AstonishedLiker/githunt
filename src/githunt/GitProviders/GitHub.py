"""
# GitHub

This file hosts the necessary code to retrieve user information from the git host GitHub.
"""

from typing import Optional
from loguru import logger

import requests
import json
import time

from githunt.Classes.RepositoryInformation import RepositoryInformation
from githunt.Classes.User import User

def http_json_get(url: str, pat: Optional[str]):
    headers = {"Authorization": f"token {pat}"} if pat else None

    while True:
        response = requests.get(url, headers=headers)

        logger.trace("HTTP Status {}", response.status_code)
        logger.trace("Response Body:\n{}", response.text)

        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")

            if remaining == "0" and reset is not None:
                reset_ts = int(reset)
                now = int(time.time())
                sleep_for = max(reset_ts - now, 0) + 1

                logger.warning(
                    "Rate limit exceeded; sleeping for {} seconds until reset",
                    sleep_for
                )

                time.sleep(sleep_for)
                continue

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            sleep_for = int(retry_after) if retry_after else 60

            logger.warning(
                "Secondary rate limit hit; sleeping for {} seconds",
                sleep_for
            )

            time.sleep(sleep_for)
            continue

        if not response.ok:
            logger.error("The response is not ok (response.ok is False)")
            return None

        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            logger.exception(
                "The response JSON appears malformed (json.loads raised json.decoder.JSONDecodeError)"
            )
            return None

def scan_repositories(user: User, repos_url: str, scan_forks: bool, personal_access_token: str) -> None:
    page = 1
    while True:
        # The API is paginated.
        repos_url = f'{repos_url}?per_page=100&page={page}&type=owner'
        repos_list = http_json_get(repos_url, personal_access_token)
        if repos_list is None:
            logger.debug("repos_list is None")
            return

        for repo_basic_info in repos_list:
            if (not scan_forks) and repo_basic_info["fork"]:
                logger.warning(
                    "Skipping the scan of the fork '{}' (use '--scan-forks' to scan forks)",
                    repo_basic_info["full_name"]
                )
                continue

            logger.debug("Scanning repository '{}'", repo_basic_info["full_name"])

            repo_full_info = http_json_get(repo_basic_info["url"], personal_access_token)
            if repo_full_info is None:
                logger.debug("repo_full_info is None")
                return

            repo = RepositoryInformation(
                repo_basic_info["full_name"],
                repo_basic_info.get("description"),
                repo_full_info["homepage"] if repo_full_info["homepage"] != "" else None,
                repo_full_info["stargazers_count"],
                repo_full_info["forks_count"],
                repo_full_info["watchers_count"],
                repo_full_info["clone_url"]
            )

            user.repositories.append(repo)
            logger.trace(repo.__dict__)
            logger.info(
                "Added repository '{}' with {} stargazers to list",
                repo.name,
                repo.stars
            )

        if len(repos_list) < 100:
            break
        page += 1

def query_user(username: str, scan_forks: bool, scan_orgs: bool, blacklisted_orgs: list[str], personal_access_token: str) -> Optional[User]:
    logger.debug("Querying user {}", username)
    user_info = http_json_get(f"https://api.github.com/users/{username}", personal_access_token)
    if user_info is None:
        logger.debug("user_info is None")
        return

    user = User(
        user_info["id"],
        user_info["login"], # corrected username (if needed)
        user_info["name"],
        user_info.get("bio"),
        user_info.get("location"),
        user_info.get("blog"),
        user_info.get("email"),
        user_info["followers"],
        user_info["following"],
        user_info["public_repos"]
    )
    logger.trace(user.__dict__)

    scan_repositories(user, user_info["repos_url"], scan_forks, personal_access_token)
    if not scan_orgs:
        logger.warning("Not scanning organizations (as requested with '--no-scan-orgs')")
        return user

    orgs_info = http_json_get(user_info["organizations_url"], personal_access_token)
    if orgs_info is None:
        logger.debug("orgs_info is None")
        logger.warning("Querying organizations failed, but the bare minimum information required is present. Skipping organization scanning")
        return user

    logger.debug("Scanning organizations..")

    for org_info in orgs_info:
        if org_info["login"] in blacklisted_orgs:
            logger.warning("Skipping scanning blacklisted organization {}", org_info["login"])
            continue
        scan_repositories(user, org_info["repos_url"], scan_forks, personal_access_token)

    return user
