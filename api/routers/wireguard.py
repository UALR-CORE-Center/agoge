import time
from fastapi import APIRouter, Depends, HTTPException, Path, Response, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import ValidationError

from common.exceptions import BadRequest, Conflict, NotFound, NotReady, Unauthorized
from common.models.response import AgogeResponse
from common.models.wireguard import WireGuardPublicEndpointModel
from common.models.wireguard_provisioning import WireGuardHealthReport, WireGuardKitCreate
from common.services.wireguard_endpoint import WireGuardEndpointRegistry
from common.services.wireguard_provisioning import WireGuardProvisioningService
from dependencies import get_cloud_env, teacher_required, admin_required


wireguard_router = APIRouter(prefix='/wireguard', tags=['wireguard'])
kit_bearer = HTTPBearer(auto_error=False)


def _token(credentials):
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Bearer device credentials are required', headers={'Cache-Control': 'no-store'})
    return credentials.credentials


def _http_error(error):
    code = 401 if isinstance(error, Unauthorized) else 409 if isinstance(error, (Conflict, NotReady)) else 404 if isinstance(error, NotFound) else 400
    return HTTPException(status_code=code, detail=str(error), headers={'Cache-Control': 'no-store'})


@wireguard_router.get('/endpoints/{peer_id}/')
async def resolve_wireguard_endpoint(
    response: Response,
    peer_id: str = Path(..., pattern=r'^[1-9][0-9]{4}$'),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[WireGuardPublicEndpointModel]:
    """Resolve a locator; a lab number is never a device credential."""
    try:
        registry = WireGuardEndpointRegistry(env_dict=env_dict)
        record = registry.get(peer_id=peer_id, public_only=True)
        provisioning = WireGuardProvisioningService(env_dict, db=registry.db)
        try:
            lease = provisioning.get_lease(record.unit_id)
        except NotFound:
            lease = None  # Existing explicitly unmanaged gateway compatibility.
        if lease and not lease.is_ready(time.time()):
            raise NotFound('WireGuard endpoint is not ready')
        # Never cache readiness: a stopped/revoked gateway must disappear at once.
        response.headers['Cache-Control'] = 'no-store'
        return AgogeResponse(data=WireGuardPublicEndpointModel.from_record(record))
    except (NotFound, BadRequest) as error:
        raise _http_error(error)


@wireguard_router.get('/kits/')
async def list_wireguard_kits(
    env_dict: dict = Depends(get_cloud_env), current_user=Depends(teacher_required),
):
    service = WireGuardProvisioningService(env_dict)
    kits = service.list_kits(current_user)
    return AgogeResponse(data={'items': kits, 'total': len(kits)})


@wireguard_router.post('/kits/', status_code=201)
async def enroll_wireguard_kit(
    data: WireGuardKitCreate, response: Response,
    env_dict: dict = Depends(get_cloud_env), current_user=Depends(admin_required),
):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return AgogeResponse(data=WireGuardProvisioningService(env_dict).enroll(data, current_user))
    except (BadRequest, Conflict, Unauthorized) as error:
        raise _http_error(error)


@wireguard_router.post('/labs/', status_code=201)
async def create_wireguard_lab(
    data: dict, env_dict: dict = Depends(get_cloud_env), current_user=Depends(teacher_required),
):
    from core.wireguard_lab import WireGuardLab
    try:
        build_id = WireGuardLab(env_dict=env_dict).build(requester=current_user, data=data)
        return AgogeResponse(data={'build_id': build_id})
    except (BadRequest, Conflict, NotFound, Unauthorized, ValidationError) as error:
        raise _http_error(error)


@wireguard_router.get('/kits/{kit_id}/configuration/')
async def get_pi_configuration(
    response: Response, kit_id: str = Path(..., pattern=r'^[a-z][a-z0-9-]{0,39}$'),
    credentials: HTTPAuthorizationCredentials | None = Security(kit_bearer),
    env_dict: dict = Depends(get_cloud_env),
):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return AgogeResponse(data=WireGuardProvisioningService(env_dict).pi_configuration(kit_id, _token(credentials)))
    except (BadRequest, NotFound, NotReady, Unauthorized) as error:
        raise _http_error(error)


@wireguard_router.post('/gateways/{unit_id}/health/')
async def report_gateway_health(
    report: WireGuardHealthReport, response: Response,
    unit_id: str = Path(..., pattern=r'^[a-z]{10}$'),
    credentials: HTTPAuthorizationCredentials | None = Security(kit_bearer),
    env_dict: dict = Depends(get_cloud_env),
):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return AgogeResponse(data=WireGuardProvisioningService(env_dict).report_health(unit_id, _token(credentials), report))
    except (BadRequest, NotFound, NotReady, Unauthorized) as error:
        raise _http_error(error)
