from typing import Any, Optional

import requests
from fastapi import APIRouter, Body, Depends, HTTPException

from common.exceptions.agoge import AgogeValidationError
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from core.puzzle_control import PuzzleControl
from dependencies import get_cloud_env, teacher_required

logger = Logger(LoggerNames.API)

# Every route drives the Govee devices or reads/writes trivia tests (including join codes),
# and the player pages are instructor-only, so the whole router requires an instructor.
puzzle_control_router = APIRouter(prefix="/puzzle-control", dependencies=[Depends(teacher_required)])

# Handlers are sync so FastAPI runs them in its threadpool: PuzzleControl makes blocking
# Firestore, Secret Manager and Govee (requests) calls.


def _failed(action: str, e: Exception) -> HTTPException:
    """Log an unexpected failure and return an error that does not echo its text, which can
    carry Govee responses or internal details."""
    if isinstance(e, requests.RequestException):
        logger.error(f"Govee request failed: {action}", error=str(e))
        return HTTPException(status_code=502, detail=f"Failed to {action}: lighting service error")
    logger.error(f"Puzzle control failed: {action}", error=str(e))
    return HTTPException(status_code=500, detail=f"Failed to {action}")


@puzzle_control_router.get("/")
def list_devices(env_dict: dict = Depends(get_cloud_env)) -> dict:
    """
    Returns all Govee devices linked to the API key stored in Google Secret Manager.
    """
    try:
        devices = PuzzleControl(env_dict=env_dict).list_devices()
    except Exception as e:
        raise _failed("list devices", e)

    if not devices:
        return {"message": "No devices found or API key not valid", "devices": []}
    return {"devices": devices}


@puzzle_control_router.post("/test/")
def create_test(
        title: str = Body(...),
        questions: list[dict] = Body(...),
        sku: str = Body(...),
        device: str = Body(...),
        env_dict: dict = Depends(get_cloud_env),
) -> dict:
    try:
        return PuzzleControl(env_dict=env_dict).create_test(
            title=title,
            questions=questions,
            sku=sku,
            device=device,
        )
    except AgogeValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise _failed("create test", e)


@puzzle_control_router.get("/test/")
def get_tests(env_dict: dict = Depends(get_cloud_env)) -> dict:
    try:
        tests = PuzzleControl(env_dict=env_dict).get_tests()
    except Exception as e:
        raise _failed("get tests", e)
    return {"tests": tests}


@puzzle_control_router.get("/test/{join_code}")
def get_test(join_code: str, env_dict: dict = Depends(get_cloud_env)) -> dict:
    try:
        test = PuzzleControl(env_dict=env_dict).get_test(join_code)
    except Exception as e:
        raise _failed("get test", e)

    if not test:
        raise HTTPException(status_code=404, detail="No tests found")
    return {"test": test}


@puzzle_control_router.post("/question/check")
def check_question_answer(
        test_id: Optional[str] = Body(None),
        question_id: Optional[str] = Body(None),
        answer: Optional[str] = Body(None),
        env_dict: dict = Depends(get_cloud_env),
) -> dict:
    """
    Check if a student's submitted answer is correct.
    Expects JSON body:
    {
        "test_id": "test-id",
        "question_id": "question-id",
        "answer": "student's submitted answer"
    }
    """
    if not test_id or not question_id or answer is None:
        raise HTTPException(status_code=400, detail="'test_id', 'question_id' and 'answer' are required.")

    try:
        result = PuzzleControl(env_dict=env_dict).check_answer(question_id, answer, test_id)
    except Exception as e:
        raise _failed("check answer", e)

    if not result:
        raise HTTPException(status_code=404, detail="Question not found")
    return result


@puzzle_control_router.post("/control")
def control_device(
        sku: Optional[str] = Body(None),
        device: Optional[str] = Body(None),
        action: Optional[Any] = Body(None),
        actions: Optional[list] = Body(None),
        env_dict: dict = Depends(get_cloud_env),
) -> dict:
    if not sku or not device:
        raise HTTPException(status_code=400, detail="Missing 'sku' or 'device'")

    # Accept one action or many
    if action and actions:
        raise HTTPException(status_code=400, detail="Use either 'action' or 'actions', not both.")
    if action:
        actions = [action]
    if not actions:
        raise HTTPException(status_code=400, detail="Provide 'action' or 'actions'.")

    def to_capability(pair):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise HTTPException(status_code=400, detail=f"Invalid action format: {pair}. Expected [name, value].")
        name, value = pair

        # --- Power on/off ---
        if name == "switchOnOff":
            if value not in [0, 1, True, False]:
                raise HTTPException(status_code=400, detail="switchOnOff expects 0/1 or False/True")
            return {
                "type": "devices.capabilities.on_off",
                "instance": "powerSwitch",  # matches your script
                "value": 1 if bool(value) else 0,
            }

        # --- Brightness 1..100 ---
        if name == "brightness":
            try:
                level = int(value)
            except Exception:
                raise HTTPException(status_code=400, detail="brightness expects an integer 1–100")
            level = max(1, min(100, level))
            return {
                "type": "devices.capabilities.range",
                "instance": "brightness",
                "value": level,
            }

        # --- RGB as [r,g,b] | "#rrggbb" | 0xRRGGBB ---
        if name == "switchColor":
            if isinstance(value, (list, tuple)) and len(value) == 3:
                try:
                    r, g, b = [int(v) for v in value]
                except Exception:
                    raise HTTPException(status_code=400, detail="RGB values must be integers")
            elif isinstance(value, str) and value.startswith("#") and len(value) == 7:
                try:
                    r = int(value[1:3], 16)
                    g = int(value[3:5], 16)
                    b = int(value[5:7], 16)
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid hex RGB string")
            elif isinstance(value, int):
                if not (0 <= value <= 0xFFFFFF):
                    raise HTTPException(status_code=400, detail="Packed RGB int out of range")
                r = (value >> 16) & 0xFF
                g = (value >> 8) & 0xFF
                b = value & 0xFF
            else:
                raise HTTPException(status_code=400, detail="switchColor expects [r,g,b], '#rrggbb', or 0xRRGGBB")

            for v in (r, g, b):
                if not (0 <= v <= 255):
                    raise HTTPException(status_code=400, detail="RGB values must be 0–255")
            rgb_int = ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)
            return {
                "type": "devices.capabilities.color_setting",
                "instance": "colorRgb",
                "value": rgb_int,
            }

        if name == "musicMode":
            if not isinstance(value, dict) or "musicMode" not in value:
                raise HTTPException(status_code=400,
                                    detail="musicMode expects an object: { musicMode: <int>, sensitivity?:0-100, autoColor?:0|1, rgb?:0xRRGGBB }")
            try:
                mode = int(value["musicMode"])
            except Exception:
                raise HTTPException(status_code=400, detail="musicMode.musicMode must be an integer")
            sensitivity = value.get("sensitivity", 50)
            try:
                sensitivity = int(sensitivity)
            except Exception:
                raise HTTPException(status_code=400, detail="musicMode.sensitivity must be an integer 0–100")
            sensitivity = max(0, min(100, sensitivity))
            auto_color = value.get("autoColor", 1)
            if auto_color not in (0, 1, True, False):
                raise HTTPException(status_code=400, detail="musicMode.autoColor must be 0/1 or False/True")
            auto_color = 1 if bool(auto_color) else 0
            out = {
                "musicMode": mode,
                "sensitivity": sensitivity,
                "autoColor": auto_color,
            }
            if "rgb" in value:
                try:
                    rgb = int(value["rgb"])
                except Exception:
                    raise HTTPException(status_code=400, detail="musicMode.rgb must be an integer 0..16777215")
                if not (0 <= rgb <= 0xFFFFFF):
                    raise HTTPException(status_code=400, detail="musicMode.rgb out of range 0..16777215")
                out["rgb"] = rgb
            return {
                "type": "devices.capabilities.music_setting",
                "instance": "musicMode",
                "value": out,
            }

        # --- Color temperature in Kelvin ---
        if name == "colorTemperatureK":
            try:
                kelvin = int(value)
            except Exception:
                raise HTTPException(status_code=400, detail="colorTemperatureK expects an integer in Kelvin")
            kelvin = max(2000, min(9000, kelvin))  # same clamp as your script
            return {
                "type": "devices.capabilities.color_setting",
                "instance": "colorTemperatureK",
                "value": kelvin,
            }

        # --- Dynamic Mode ---
        if name == "lightScene":
            try:
                scene = int(value)
            except Exception:
                raise HTTPException(status_code=400, detail="lightScene expects an integer")
            return {
                "type": "devices.capabilities.dynamic_scene",
                "instance": "lightScene",
                "value": scene,
            }

        raise HTTPException(status_code=400, detail=f"Unsupported action type: {name}")

    caps = [to_capability(a) for a in actions]

    try:
        lamp = PuzzleControl(env_dict=env_dict)
        results = []
        for cap in caps:
            res = lamp.control_device(sku=sku, device=device, capability=cap)
            results.append({"capability": cap, "result": res})
    except Exception as e:
        raise _failed("control device", e)

    return {
        "status": "ok",
        "applied": {
            "sku": sku,
            "device": device,
            "count": len(caps),
            "capabilities": caps,
        },
        "results": results,
    }
