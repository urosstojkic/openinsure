"""API authentication — redirects to openinsure.rbac.auth.

Kept for backwards compatibility. New code should import from
``openinsure.rbac.auth`` directly.
"""

from openinsure.rbac.auth import CurrentUser, get_current_user, require_roles

__all__ = ["CurrentUser", "get_current_user", "require_roles"]
