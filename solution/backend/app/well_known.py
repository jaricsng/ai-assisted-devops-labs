from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

# RFC 9116 security.txt — update Contact and Expires before going to production.
# Expires must be an ISO 8601 datetime; set it ~1 year from your deployment date.
SECURITY_TXT = """\
Contact: mailto:security@example.com
Expires: 2027-01-01T00:00:00.000Z
Preferred-Languages: en
Policy: https://github.com/YOUR_USERNAME/task-manager/blob/main/SECURITY.md
"""


@router.get(
    "/.well-known/security.txt",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def security_txt() -> str:
    """Responsible disclosure endpoint (RFC 9116)."""
    return SECURITY_TXT
