from typing import Union

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response
)

from common.exceptions import NotFound, BadRequest, ServiceUnavailable, AgogeValidationError, NotReady
from common.models.agoge import AgogeImageModel
from common.models.users import AgogeUser
from common.models.response import (
    AgogeResponse,
    AgogeIDResponse,
    ImageListResponse,
    ComputeImageListResponse,
    GoogleImageListResponse,
    MachineTypeListResponse
)
from common.constants.enumerators import ImageScopes
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.compute.image import ComputeImage
from dependencies import teacher_required, admin_required, get_cloud_env


compute_image_router = APIRouter(prefix="/compute/images")
logger = Logger(LoggerNames.API)


@compute_image_router.get("/")
async def list_images(
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[ImageListResponse]:
    log_args = {
        'user': current_user.uid,
    }

    try:
        images = ComputeImage(env_dict=env_dict).list_images()
        return AgogeResponse(data={'items': images})
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400)


@compute_image_router.post("/")
async def process_image_list_action(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }

    json_data = await request.json()
    try:
        logger.info(f'POST request initiated by {current_user.uid}', **log_args)
        ComputeImage(env_dict=env_dict).process_action_on_list(
            current_user.email,
            json_data
        )
        return Response(status_code=200)
    except BadRequest as e:
        logger.error(f'action on image list failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except NotReady as e:
        logger.error(f"action on image list failed with reason: {e.message}", **log_args)
        raise HTTPException(status_code=503, detail=e.message)


@compute_image_router.get("/project/")
async def list_project_images(
    env_dict: dict = Depends(get_cloud_env),
    scope: ImageScopes = ImageScopes.PROJECT,
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[Union[GoogleImageListResponse, ComputeImageListResponse]]:
    log_args = {
        'user': current_user.uid,
        'scope': scope
    }

    try:
        images = ComputeImage(env_dict=env_dict).list_project_images(scope=scope)
        if scope == ImageScopes.GLOBAL:
            return AgogeResponse(data={'items': images})
        else:
            return AgogeResponse(data=images)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)


@compute_image_router.get('/machine-types/')
async def list_machine_types(
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[MachineTypeListResponse]:
    log_args = {
        'user': current_user.uid,
    }
    try:
        machine_types = ComputeImage(env_dict=env_dict).machine_types()
        return AgogeResponse(data={'items': machine_types})
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404)


@compute_image_router.get("/{image_name}/")
async def get_image(
    image_name: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeImageModel]:
    log_args = {
        'user': current_user.uid,
        'image': image_name
    }

    try:
        image = ComputeImage(env_dict=env_dict).get(image_name)
        return AgogeResponse(data=image)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)


@compute_image_router.get("/{image_name}/state/")
async def get_image_state(
    image_name: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeIDResponse]:
    """
    Retrieves current state of compute image

    Returns: `{'build_id': image_name, 'state': image.get('state')}`
    """
    log_args = {
        'user': current_user.uid,
        'image': image_name
    }

    try:
        image_status = ComputeImage(env_dict=env_dict).get_image_state(image_name)
        return AgogeResponse(data=image_status)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404)
    except ServiceUnavailable as e:
        msg = e.message if e.message else "Image is not ready"
        logger.error(msg, **log_args)
        raise HTTPException(status_code=503, detail="Image is not ready")


@compute_image_router.post("/create/")
async def create_image_server(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }

    json_data = await request.json()
    try:
        logger.info(f'POST request to create image server from user, {current_user.uid}', **log_args)
        ComputeImage(env_dict=env_dict).create_image_server(
            current_user,
            json_data
        )
        return Response(status_code=200)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
    except (BadRequest, AgogeValidationError) as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)


@compute_image_router.post("/project/")
async def update_project_images(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(admin_required)
) -> AgogeResponse[GoogleImageListResponse]:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }

    json_data = await request.json()
    try:
        logger.info(f'POST request to update project images from user {current_user.uid}', **log_args)
        updated_images = ComputeImage(env_dict=env_dict).update_project_images(json_data)
        return AgogeResponse(data={'items': updated_images})
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)


@compute_image_router.put("/{image_name}/")
async def process_image_action(
    request: Request,
    image_name: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'user': current_user.uid,
        'image': image_name,
        'origin': request.client.host
    }

    json_data = await request.json()
    if json_data:
        try:
            logger.info(f"PUT request for image action from user {current_user.uid}", **log_args)
            ComputeImage(env_dict=env_dict).process_action_on_image(
                requester=current_user,
                data=json_data,
                server_name=image_name,
            )
            return Response(status_code=200)
        except NotFound as e:
            logger.error(e.message, **log_args)
            raise HTTPException(status_code=404)
        except (BadRequest, AgogeValidationError) as e:
            logger.error(e.message, **log_args)
            raise HTTPException(status_code=400)
    else:
        error_msg = 'Invalid or missing data in request'
        logger.error(error_msg, **log_args)
        raise HTTPException(status_code=400, detail=error_msg)


@compute_image_router.delete("/{image_name}/")
async def delete_image(
    request: Request,
    image_name: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(admin_required)
) -> Response:
    log_args = {
        'image': image_name,
        'user': current_user.uid,
        'origin': request.client.host
    }

    try:
        logger.info(f'DELETE request for image {image_name} from user {current_user.uid}', **log_args)
        ComputeImage(env_dict).delete(image_name)
        return Response(status_code=200)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404)


@compute_image_router.patch("/{image_name}/")
async def update_image(
    request: Request,
    image_name: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'user': current_user.uid,
        'image': image_name,
        'origin': request.client.host
    }
    json_data = await request.json()

    try:
        logger.info(f"PATCH request for {image_name} from user {current_user.uid}", **log_args)
        ComputeImage(env_dict).update_image(image_name, json_data)
        return Response(status_code=200)
    except NotFound as e:
        logger.error(f"update_image - {e.message}", **log_args)
        raise HTTPException(status_code=404, detail="Requested image not found!")
    except BadRequest as e:
        logger.error(f"update_image - {e.message}", **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except AgogeValidationError as e:
        logger.error(f"update_image - Failed with validation errors.", errors=e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"update_image - {e}", **log_args)
        raise HTTPException(status_code=500, detail="Something went wrong!")


