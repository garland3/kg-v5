import logging
from app.config import TEST_USER_BELONGS_TO_AUTHORIZATION_GROUP

def check_user_authorization_groups(user_email: str) -> list:
    """
    Mock function to check which authorization groups a user belongs to.
    
    In a real implementation, this would call an external service or API
    to get the user's authorization groups. For testing purposes, we're
    returning a hardcoded value from the environment variable.
    
    Args:
        user_email: The email of the user to check
        
    Returns:
        A list of authorization groups the user belongs to
    """
    logging.info(f"Checking authorization groups for user: {user_email}")
    
    # In a real implementation, this would call an external service
    # For now, we'll return the test authorization group from config
    return [TEST_USER_BELONGS_TO_AUTHORIZATION_GROUP]

def is_user_in_group(user_email: str, group_name: str) -> bool:
    """
    Check if a user is in a specific authorization group.
    
    Args:
        user_email: The email of the user to check
        group_name: The name of the authorization group to check
        
    Returns:
        True if the user is in the group, False otherwise
    """
    user_groups = check_user_authorization_groups(user_email)
    return group_name in user_groups
