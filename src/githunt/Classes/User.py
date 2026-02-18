from typing import Optional
from loguru import logger

import re

from githunt.Classes.RepositoryInformation import RepositoryInformation
from githunt.Classes.GitData import GitData

class User:
    def __init__(
        self,

        id: int,

        username: str,
        displayname: str,
        description: Optional[str],
        location: Optional[str],
        personal_link: Optional[str],
        email: Optional[str],

        followers: int,
        following: int,
        total_repository_count: int
    ) -> None:
        self.id: int = id

        self.name: str = username
        self.displayname: str = displayname
        self.description: Optional[str] = description
        self.location: Optional[str] = location
        self.personal_link: Optional[str] = personal_link

        if email is str and re.match(r"[^@]+@[^@]+\.[^@]+", email):
            logger.debug("The user appears to have a valid email in meta links")
            self.email: Optional[str] = email
        else:
            self.email: Optional[str] = None

        self.followers: int = followers
        self.following: int = following
        self.total_repository_count: int = total_repository_count

        self.repositories: list[RepositoryInformation] = []
        self.git_data: GitData = GitData(self)
