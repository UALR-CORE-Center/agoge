from fastapi import APIRouter, Depends, UploadFile, HTTPException, Request, Response, File
from urllib.parse import unquote
from pydantic import ValidationError

from common.exceptions import NotFound, BadRequest, AgogeValidationError, ContentTooLarge
from common.models.users import AgogeUser
from common.models.response import (
    AgogeResponse,
    AgogeIDResponse,
    LabSpecListResponse,
    StartupScriptListResponse, CatalogEditListResponse
)
from common.models.agoge import CatalogModel, CatalogEditModel
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.specifications.lab_specs import LabSpecs
from core.specifications.lab_spec_edit import LabSpecsEdit
from dependencies import (
    teacher_required,
    admin_required,
    get_cloud_env,
)

lab_spec_router = APIRouter(prefix="/lab-specs")
logger = Logger(LoggerNames.API)


# Base LabSpec routes
@lab_spec_router.get("/")
async def list_specs(
        env_dict: dict = Depends(get_cloud_env),
        _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[LabSpecListResponse]:
    try:
        specs = LabSpecs(env_dict).list()
        return AgogeResponse(data={'items': specs})
    except NotFound:
        raise HTTPException(status_code=404)


@lab_spec_router.post("/", description="Creates a blank Catalog specification object editing.")
async def create(
    env_dict: dict = Depends(get_cloud_env),
    user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[AgogeIDResponse]:
    """
    Processes action on specification based on `spec_action` in submitted JSON object

    Returns: `{'build_id': edit_id}`
    """
    try:
        logger.info(f'POST request for lab_specs.create from user {user.uid}', user=user.uid)
        spec_id = LabSpecsEdit(env_dict).create(requester=user)
        return AgogeResponse(data=spec_id)
    except BadRequest as e:
        logger.error(e.message, user=user.uid)
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        logger.error(e.message, user=user.uid)
        raise HTTPException(status_code=404, detail=e.message)


@lab_spec_router.get('/startup-scripts/')
async def list_startup_scripts(
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[StartupScriptListResponse]:
    try:
        scripts = LabSpecs(env_dict).list_startup_scripts()
        return AgogeResponse(data={'items': scripts})
    except NotFound as e:
        raise HTTPException(status_code=404)


@lab_spec_router.post('/startup-scripts/')
async def upload_startup_script(
    request: Request,
    file: UploadFile,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }

    form_data = await request.form()
    try:
        logger.info(f'POST request to upload_startup_script from user {current_user.uid}', **log_args)
        uploaded_file_name = await LabSpecs(env_dict).upload_script(file, form_data)
        return AgogeResponse(data=uploaded_file_name)
    except (BadRequest, AgogeValidationError, ValidationError) as e:
        if isinstance(e, ValidationError):
            msg = str(e)
        else:
            msg = e.message
        logger.error(msg, **log_args)
        raise HTTPException(status_code=400, detail=msg)


@lab_spec_router.post("/upload/", description="Creates a new Catalog specification from an uploaded file.")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    """
    Create a new specification from file upload.
    Expects JSON format.

    Returns: `{'spec': spec}`
    """
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }
    form_data = await request.form()

    try:
        logger.info(f'POST request to upload specification from user {current_user.uid}', **log_args)
        await LabSpecs(env_dict).upload_file(file, form_data)
        return Response(status_code=200)
    except (BadRequest, AgogeValidationError, ValidationError) as e:
        if isinstance(e, ValidationError):
            msg = str(e)
        else:
            msg = e.message
        logger.error(msg, **log_args)
        raise HTTPException(status_code=400, detail=msg)
    except ContentTooLarge as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=413, detail=e.message)


@lab_spec_router.get("/edit/")
async def list_edits_specs(
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[CatalogEditListResponse]:
    try:
        specs = LabSpecsEdit(env_dict).list()
        return AgogeResponse(data={'items': specs})
    except NotFound:
        raise HTTPException(status_code=404)


@lab_spec_router.get('/edit/{edit_id}/')
async def get_specification_edit(
    edit_id: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[CatalogEditModel]:
    try:
        spec = LabSpecsEdit(env_dict).get(edit_id)
        return AgogeResponse(data=spec)
    except NotFound as e:
        logger.error(e.message, edit_id=edit_id, user=current_user.uid)
        raise HTTPException(status_code=400, detail=e.message)


@lab_spec_router.post('/edit/{edit_id}/')
async def edit_specification(
    request: Request,
    edit_id: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse:
    log_args = {
        'user': current_user.uid,
        'edit_id': edit_id,
        'origin': request.client.host
    }

    json_data = await request.json()
    try:
        logger.info(f'POST request to edit_specification from user {current_user.uid}', **log_args)
        spec = LabSpecsEdit(env_dict).edit(edit_id, json_data)
        return AgogeResponse(data=spec)
    except ValueError as e:
        logger.error(str(e), **log_args)
        raise HTTPException(status_code=500, detail="Server could not process request")
    except (AgogeValidationError, ValidationError) as e:
        if isinstance(e, ValidationError):
            msg = str(e)
        else:
            msg = e.message
        logger.error(msg, **log_args)
        raise HTTPException(status_code=400, detail=msg)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)


@lab_spec_router.delete('/edit/{edit_id}/')
async def delete_edit(
    edit_id: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'edit_id': edit_id,
        'user': current_user.uid
    }

    try:
        logger.info(
            f'DELETE request for specification edit with id {edit_id} from user {current_user.uid}',
            **log_args
        )
        LabSpecsEdit(env_dict).delete_edit(edit_id)
        return Response(status_code=200)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)


@lab_spec_router.get("/{spec_id}/")
async def get_spec(
    spec_id: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[CatalogModel]:
    decoded_id = unquote(spec_id)
    try:
        spec = LabSpecs(env_dict).get(decoded_id)
        return AgogeResponse(data=spec)
    except NotFound as e:
        logger.error(e.message, spec_id=str(decoded_id), user=current_user.uid)
        raise HTTPException(status_code=404, detail=e.message)


@lab_spec_router.post(
    "/{spec_id}/",
    description="Create a copy or edit object for an existing Catalog specification"
)
async def process_action(
    request: Request,
    spec_id: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeIDResponse]:
    """
    Processes action on specification based on `spec_action` in submitted JSON object

    Returns: `{'build_id': edit_id}`
    """
    decoded_id = unquote(spec_id)
    json_data = await request.json()
    log_args = {
        'user': current_user.uid,
        'spec_id': decoded_id,
        'origin': request.client.host,
    }
    try:
        logger.info(
            f'POST request received to copy or edit specification with id {spec_id} from user {current_user.uid}',
            **log_args
        )
        spec_id = (
            LabSpecsEdit(env_dict=env_dict)
            .process_action(decoded_id, json_data, requester=current_user)
        )
        return AgogeResponse(data=spec_id)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except ValueError as e:
        logger.error(str(e), **log_args)
        raise HTTPException(status_code=400, detail=str(e))
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)


@lab_spec_router.delete("/{spec_id}/")
async def delete(
    spec_id: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(admin_required)
) -> Response:
    decoded_id = unquote(spec_id)
    log_args = {
        'spec_id': decoded_id,
        'user': current_user.uid
    }
    try:
        logger.info(
            f'DELETE request for specification with id {decoded_id} from user {current_user.uid}',
            **log_args
        )
        LabSpecs(env_dict).delete(decoded_id)
        return Response(status_code=200)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
