from fastapi import APIRouter, Depends, HTTPException, UploadFile, Request

from common.exceptions import NotFound, BadRequest, Unauthorized, AgogeValidationError
from common.models.agoge import AgogeInstructionsModel
from common.models.response import AgogeResponse, AgogeInstructionsImageResponse, AgogeInstructionsResponse, \
    AgogeInstructionsMinimalResponse
from common.models.users import AgogeUser
from common.constants.database import DbCollections

from core.docs import Docs
from dependencies import (
    get_cloud_env,
    teacher_required
)

docs_router = APIRouter(
    prefix="/docs"
)


@docs_router.get("/student/{build_id}/")
async def get_student(
    build_id: str,
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse:
    try:
        resp = (
            await Docs(env_dict=env_dict)
            .get_instructions(
                build_id=build_id,
                build_type=DbCollections.WORKOUT
            )
        )
        return AgogeResponse(data=resp)
    except BadRequest as e:
        raise HTTPException(400, detail=e.message)
    except Unauthorized as e:
        raise HTTPException(401, detail=e.message)
    except NotFound as e:
        raise HTTPException(404, detail=e.message)


@docs_router.get("/teacher/{build_id}/")
async def get_teacher(
    build_id: str,
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse:
    try:
        resp = (
            await Docs(env_dict=env_dict)
            .get_instructions(
                build_id=build_id,
                build_type=DbCollections.UNIT
            )
        )
        return AgogeResponse(data=resp)
    except BadRequest as e:
        raise HTTPException(400, detail=e.message)
    except NotFound as e:
        raise HTTPException(404, detail=e.message)


@docs_router.get(
    "/instructions/{uid}/",
    description="Fetch specific file with uid in database"
)
async def get_single_instruction(
    uid: str,
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeInstructionsModel]:
    try:
        instructions = Docs(env_dict=env_dict).get_markdown_instruction(uid=uid)
        return AgogeResponse(data=instructions)
    except (BadRequest, AgogeValidationError) as e:
        raise HTTPException(status_code=400, detail=e.message)


@docs_router.get(
    "/instructions/",
    description="List stripped instructions"
)
async def list_instructions(
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeInstructionsMinimalResponse]:
    try:
        instructions = Docs(env_dict=env_dict).list_instructions()
        return AgogeResponse(data={'items': instructions})
    except (BadRequest, AgogeValidationError) as e:
        raise HTTPException(status_code=400, detail=e.message)


@docs_router.get(
    "/instructions/full",
    description="List all instructions currently stored in database"
)
async def list_instructions_full(
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeInstructionsResponse]:
    try:
        instructions = Docs(env_dict=env_dict).list_instructions_full()
        return AgogeResponse(data={'items': instructions})
    except (BadRequest, AgogeValidationError) as e:
        raise HTTPException(status_code=400, detail=e.message)


@docs_router.post(
    "/instructions/",
    description="Create an instructions template for edits."
)
async def create_instructions(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse:
    form_data = await request.json()
    try:
        uid = Docs(env_dict=env_dict).create_instructions(form_data)
        return AgogeResponse(data={'uid': uid})
    except (BadRequest, AgogeValidationError) as e:
        raise HTTPException(status_code=400, detail=e.message)


@docs_router.post(
    "/instructions/images/",
    description="Upload images to use in Markdown documents"
)
async def upload_images(
    request: Request,
    file: UploadFile,
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeInstructionsImageResponse]:
    form_data = await request.form()
    try:
        image_url = (
            await Docs(env_dict=env_dict)
            .upload_image(file, form_data)
        )
        return AgogeResponse(data={"image_url": image_url})
    except (BadRequest, AgogeValidationError) as e:
        raise HTTPException(status_code=400, detail=e.message)


@docs_router.post("/instructions/{uid}/")
async def edit_instructions(
    uid: str,
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    _: AgogeUser = Depends(teacher_required)
) -> AgogeResponse:
    form_data = await request.json()
    try:
        file_id = Docs(env_dict=env_dict).edit_instructions(uid, form_data)
        return AgogeResponse(data={'uid': file_id})
    except (BadRequest, AgogeValidationError) as e:
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        raise HTTPException(status_code=404, detail=e.message)