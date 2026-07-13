from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    username: str
    full_name: str
    password_hash: str
    role: str = "Admin"
    is_active: bool = True
    id: Optional[int] = None