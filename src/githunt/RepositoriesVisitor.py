from typing import Optional, TYPE_CHECKING
from loguru import logger
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from git import Repo

import subprocess
import shutil
import os

from githunt.Utils import random_str
from githunt.Classes.Alias import Alias
from githunt.Classes.User import User
from githunt.Classes.RepositoryInformation import RepositoryInformation

git_data_lock = Lock()

def matching_substrings(a: str, b: str) -> bool:
    a = a.lower()
    b = b.lower()

    return (
        a == b
        or a in b
        or b in a
    )

def normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())

def names_equivalent_strict(a: str, b: str) -> bool:
    return normalize_name(a) == normalize_name(b)

def names_equivalent_guess(a: str, b: str) -> bool:
    """
    Controlled heuristic
    It prevents 'John' matching 'Johnny' for example, or 'Alex' matching 'Alexander'
    """

    a_tokens = normalize_name(a).split()
    b_tokens = normalize_name(b).split()

    if not a_tokens or not b_tokens:
        return False

    if a_tokens == b_tokens:
        return True

    # Same first + last token (e.g. "John A Smith" vs "John Smith")
    if len(a_tokens) >= 2 and len(b_tokens) >= 2:
        return a_tokens[0] == b_tokens[0] and a_tokens[-1] == b_tokens[-1]

    return False

def expand_identities(repos: list[Repo], user: User, alias_based_inference: bool, repo_infos: list[RepositoryInformation]) -> None:
    logger.debug("Starting global identity expansion")

    changed = True
    pass_number = 0

    while changed:
        changed = False
        pass_number += 1
        logger.debug("Expansion pass {}", pass_number)

        for i in range(len(repos)):
            repo = repos[i]
            repo_info = repo_infos[i]

            try:
                for commit in repo.iter_commits():

                    author_name = commit.author.name
                    author_email = commit.author.email
                    timestamp = commit.committed_datetime

                    if TYPE_CHECKING:
                        assert author_name
                        assert author_email

                    logger.trace("[{}] Looking at commit {} from '{} <{}>'", repo_info.name, commit.hexsha[:7], author_name, author_email)

                    matching_strict_name = any(
                        alias.name.strip().lower() == author_name.strip().lower()
                        for alias in user.git_data.aliases
                    )

                    matching_strict_email = any(
                        email.strip() == author_email.strip() 
                        for email in user.git_data.emails
                    )

                    if author_name == user.name or author_name == user.displayname:
                        logger.trace("[{}] Updating is_signed status for main alias", repo_info.name)
                        main_alias = user.git_data.aliases[0]
                        if not main_alias.is_signed:
                            main_alias.is_signed = commit.gpgsig is not None

                    # Timestamp discovery
                    if (matching_strict_email):
                        logger.trace("[{}] Adding timestamp '{}'", repo_info.name, timestamp)
                        user.git_data.timestamps.append(timestamp)

                    # Email discovery
                    if (matching_strict_name) and (author_email not in user.git_data.emails):
                        logger.debug("[{}] Discovered email '{}' (matched {})", repo_info.name, author_email, author_name)
                        user.git_data.emails.add(author_email)
                        changed = True

                    # Alias discovery
                    existing_strict_alias = next(
                        (
                            alias
                            for alias in user.git_data.aliases
                            if alias.name == author_name
                        ),
                        None
                    )

                    if matching_strict_email and (not existing_strict_alias):
                        alias = Alias(
                            author_name,
                            is_main=False,
                            is_signed=(commit.gpgsig is not None),
                        )
                        logger.debug("[{}] Discovered{}alias '{}' (STRONG CONFIDENCE)", repo_info.name, alias.is_signed and " signed " or " ", alias)
                        user.git_data.aliases.append(alias)
                        changed = True
                        continue

                    if existing_strict_alias:
                        continue

                    if alias_based_inference and len(author_name) > 3 and (
                        names_equivalent_guess(user.name, author_name) or
                        matching_substrings(user.name, author_name) or
                        names_equivalent_guess(user.displayname, author_name) or
                        matching_substrings(user.displayname, author_name)
                    ):
                        alias = Alias(
                            author_name,
                            is_main=False,
                            is_signed=(commit.gpgsig is not None),
                        )
                        logger.debug("[{}] Discovered{}alias '{}' (WEAK CONFIDENCE)", repo_info.name, alias.is_signed and " signed " or " ", alias)
                        user.git_data.aliases.append(alias)
                        changed = True

            except:
                logger.exception("Failed scanning the repository (is the repository empty?)")

        logger.debug(
            "Pass {} complete - {} aliases, {} emails",
            pass_number,
            len(user.git_data.aliases),
            len(user.git_data.emails),
        )

    logger.success("Identity expansion converged after {} passes", pass_number)

def clone_repository(repo: RepositoryInformation, temp_dir_name: str) -> Optional[tuple[Repo, RepositoryInformation]]:
    try:
        logger.info("Cloning repository '{}'", repo.name)

        process = subprocess.Popen(
            ["git", "clone", repo.git_url, repo.name.replace('/', '-')],
            cwd=temp_dir_name,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate()

        for line in stdout.splitlines():
            logger.debug("Git [{}]: {}", repo.name, line)

        for line in stderr.splitlines():
            logger.debug("Git [{}]: {}", repo.name, line)

        repo_path = os.path.join(temp_dir_name, repo.name.replace('/', '-'))
        return Repo(repo_path), repo

    except Exception:
        logger.exception("Failed to clone repository '{}'", repo.name)
        return None

def visit_repositories(user: User, workers: int, alias_based_inference: bool) -> None:
    logger.debug("Visiting repositories with {} workers", workers)

    temp_dir_name = f"gitrepos_{user.name.lower()}_{random_str(16)}"
    logger.debug("Set temp dir name to '{}'", temp_dir_name)

    try:
        os.mkdir(temp_dir_name)
    except Exception:
        logger.exception("Couldn't create temporary directory")
        return

    repos: list[Repo] = []
    repo_infos: list[RepositoryInformation] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(clone_repository, repo_info, temp_dir_name)
            for repo_info in user.repositories
        ]

        for future in as_completed(futures):
            result_tuple = future.result()
            if result_tuple is None:
                continue

            repo, repo_info = result_tuple
            repos.append(repo)
            repo_infos.append(repo_info)

    logger.info("Finished cloning {} repositories", len(repos))
    expand_identities(repos, user, alias_based_inference, repo_infos)

    logger.info("Sorting timestamps for analysis later on")
    user.git_data.timestamps.sort()

    try:
        shutil.rmtree(temp_dir_name)
    except Exception:
        logger.exception("Couldn't remove temporary directory")
