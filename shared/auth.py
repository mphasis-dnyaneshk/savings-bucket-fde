from fastapi import Header, HTTPException, status


def require_customer_id(x_customer_id: str | None = Header(default=None)) -> str:
    """Temporary local identity boundary; replace with OIDC/JWT validation in R0 auth work."""
    if not x_customer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        )
    return x_customer_id
