from typing import Annotated

from app.services.auth.utils import get_current_user
from app.services.users.schema import UserData
from fastapi import APIRouter, Depends, HTTPException, Request, status
from search.search import Search

router = APIRouter(prefix="/search")

es = Search()


@router.get(
    "/",
    description="This endpoint accepts any number of query parameters. Just append them to the URL like this: ?muid1=value1&muid2=value2",  # noqa: 501
)
async def search(
    user: Annotated[UserData, Depends(get_current_user)],
    request: Request,
    uid: str | None = None,
):
    if not request.query_params:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No query parameters provided",
        )
    data = es.get_segments(**request.query_params)
    return data
