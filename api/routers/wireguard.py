from fastapi import APIRouter, Depends, HTTPException, Path, Response

from common.exceptions import BadRequest, NotFound
from common.models.response import AgogeResponse
from common.models.wireguard import WireGuardPublicEndpointModel
from common.services.wireguard_endpoint import WireGuardEndpointRegistry
from dependencies import get_cloud_env


wireguard_router = APIRouter(
    prefix="/wireguard/endpoints",
    tags=["wireguard"],
)


@wireguard_router.get("/{peer_id}/")
async def resolve_wireguard_endpoint(
    response: Response,
    peer_id: str = Path(..., pattern=r"^[1-9][0-9]{4}$"),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[WireGuardPublicEndpointModel]:
    """Resolve a public five-digit ID without exposing Unit or address metadata."""
    try:
        record = WireGuardEndpointRegistry(env_dict=env_dict).get(
            peer_id=peer_id,
            public_only=True,
        )
        # The small, cacheable response makes this endpoint friendly to an
        # API-gateway rate limit without treating the public ID as a secret.
        response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
        return AgogeResponse(data=WireGuardPublicEndpointModel.from_record(record))
    except NotFound as error:
        raise HTTPException(status_code=404, detail=error.message)
    except BadRequest as error:
        raise HTTPException(status_code=400, detail=error.message)
