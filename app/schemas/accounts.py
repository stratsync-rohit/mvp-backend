"""Minimal browser-safe account metadata for the MVP account selector."""
from pydantic import BaseModel, ConfigDict


class AccountListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accountId: str
    accountName: str
