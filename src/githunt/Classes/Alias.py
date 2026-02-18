class Alias:
    """
    We define "Alias" as a username linked to the target.

    They are discovered through e-mail matching based on the original username.
    """

    def __init__(self, name: str, is_main: bool, is_signed: bool) -> None:
        self.name: str = name
        self.is_main: bool = is_main
        self.is_signed: bool = is_signed

    def __str__(self) -> str:
        return f"<{self.name} (is_main: {self.is_main}, is_signed: {self.is_signed})>"
