from typing import TYPE_CHECKING
from datetime import datetime

from githunt.Classes.Alias import Alias

if TYPE_CHECKING:
    from githunt.Classes.User import User

class GitData:
    def __init__(self, user: User) -> None:
        self.aliases: list[Alias] = [Alias(user.name, is_main=True, is_signed=False)]
        self.emails: set[str] = set()
        self.timestamps: list[datetime] = [] # We don't mind duplicates

        self.emails.add(f"{user.id}+{user.name}@users.noreply.github.com") # Default GitHub email

        if user.email:
            self.emails.add(user.email)