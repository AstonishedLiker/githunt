from typing import Optional

class RepositoryInformation:
    def __init__(
        self,

        name: str,
        description: Optional[str],
        home_link: Optional[str],

        stars: int,
        forks: int,
        watchers: int,

        git_url: str
    ) -> None:
        self.name: str = name
        self.description: Optional[str] = description
        self.home_link: Optional[str] = home_link

        self.stars: int = stars
        self.forks: int = forks
        self.watchers: int = watchers

        self.git_url: str = git_url
