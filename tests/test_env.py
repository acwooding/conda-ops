from src.commands import check_env_exists

def test_check_env_exists():
    """
    This test checks the function check_env_exists().
    It uses an unlikely environment name to ensure that it doesn't exist.
    """
    env_name = "very_unlikely_env_name_that_doesnt_exist"
    assert check_env_exists(env_name) is False
