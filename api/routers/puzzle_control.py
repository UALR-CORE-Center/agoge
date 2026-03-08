from fastapi import APIRouter, HTTPException, Request

from core.puzzle_control import PuzzleControl
from dependencies import get_cloud_env

puzzle_control_router = APIRouter(prefix="/puzzle-control")


@puzzle_control_router.get("/")
async def list_devices() -> dict:
    """
    Returns all Govee devices linked to the API key stored in Google Secret Manager.
    """
    try:
        lamp = PuzzleControl()
        devices = lamp.list_devices()

        if not devices:
            return {"message": "No devices found or API key not valid", "devices": []}

        return {"devices": devices}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list devices: {e}")

@puzzle_control_router.post("/test/")
async def create_test(
        request: Request,
) -> dict:
    json_data = await request.json()
    title = json_data["title"]
    questions = json_data["questions"]
    sku = json_data["sku"]
    device = json_data["device"]
    try:
        puzzle = PuzzleControl()
        response = puzzle.create_test(
            title=title,
            questions=questions,
            sku=sku,
            device=device,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create test: {e}")
    return response

@puzzle_control_router.get("/test/")
async def get_tests() -> dict:
    try:
        puzzle = PuzzleControl()
        tests = puzzle.get_tests()
        if not tests:
            raise HTTPException(status_code=404, detail="No tests found or API key not valid")
        return {"tests": tests}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tests: {e}")

@puzzle_control_router.get("/test/{join_code}")
async def get_test(join_code: str) -> dict:
    try:
        puzzle = PuzzleControl()
        test = puzzle.get_test(join_code)
        if not test:
            raise HTTPException(status_code=404, detail="No tests found")
        return {"test": test}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get test: {e}")

@puzzle_control_router.post("/question/check")
async def check_question_answer(request: Request) -> dict:
    """
    Check if a student's submitted answer is correct.
    Expects JSON body:
    {
        "id": "question-id",
        "answer": "student's submitted answer"
    }
    """
    data = await request.json()
    test_id = data.get("test_id")
    question_id = data.get("question_id")
    submitted_answer = data.get("answer")
    if not question_id or submitted_answer is None:
        raise HTTPException(status_code=400, detail="Both 'id' and 'answer' are required.")

    try:
        puzzle = PuzzleControl()
        result = puzzle.check_answer(question_id, submitted_answer, test_id)
        if not result:
            raise HTTPException(status_code=404, detail="Question not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check answer: {e}")

@puzzle_control_router.post("/control")
async def control_device(request: Request) -> dict:
    json_data = await request.json()

    sku = json_data.get("sku")
    device_id = json_data.get("device")

    if not sku or not device_id:
        raise HTTPException(status_code=400, detail="Missing 'sku' or 'device'")

    # Accept one action or many
    action = json_data.get("action")
    actions = json_data.get("actions")
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

    try:
        caps = [to_capability(a) for a in actions]

        lamp = PuzzleControl()
        results = []
        for cap in caps:
            res = lamp.control_device(sku=sku, device=device_id, capability=cap)
            results.append({"capability": cap, "result": res})

        return {
            "status": "ok",
            "applied": {
                "sku": sku,
                "device": device_id,
                "count": len(caps),
                "capabilities": caps,
            },
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to control device: {e}")
