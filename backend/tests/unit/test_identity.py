from uuid import UUID

from seatsafe.config import Settings
from seatsafe.identity import get_current_user


def test_current_user_comes_from_server_settings() -> None:
    demo_user_id = UUID("00000000-0000-4000-8000-000000000002")

    current_user = get_current_user(Settings(environment="test", demo_user_id=demo_user_id))

    assert current_user.id == demo_user_id
