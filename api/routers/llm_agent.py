from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, Body, Depends

from common.models.competency_assessment_agent import AgentAttributes
from common.models.response import AgogeResponse
from common.models.users import AgogeUser
from common.constants.enumerators import LLMAgentTypes

from dependencies import admin_required, websocket_admin_required
from utilities.connection_manager import ConnectionManager
from utilities.llm.llm_agent.factory import LLMAgentFactory


llm_agent_router = APIRouter(prefix="/llm-agents")
manager = ConnectionManager()


@llm_agent_router.post("/")
def create(
    agent_attributes: AgentAttributes = Body(description="The agent attributes to create."),
    llm_agent_type: str = Query(LLMAgentTypes.openai.value, description="The LLM provider to use."),
    current_user: AgogeUser = Depends(admin_required)
) -> AgogeResponse[AgentAttributes]:
    try:
        agent = LLMAgentFactory.create_llm_agent_object(
            agent_name=agent_attributes.id,
            llm_agent_type=LLMAgentTypes(llm_agent_type)
        )
        agent.create_agent(agent_attributes=agent_attributes)
        return AgogeResponse(data=agent_attributes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@llm_agent_router.get("/{agent_name}")
def get(
    agent_name: str,
    current_user: AgogeUser = Depends(admin_required)
) -> AgogeResponse[AgentAttributes]:
    try:
        agent = LLMAgentFactory.create_llm_agent_object(agent_name=agent_name)
        return AgogeResponse(data=agent.get_agent(agent_id=agent_name))
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@llm_agent_router.put("/{agent_name}")
def update_agent(
    agent_name: str,
    agent_attributes: AgentAttributes,
    current_user: AgogeUser = Depends(admin_required)
) -> AgogeResponse[AgentAttributes]:
    try:
        agent = LLMAgentFactory.create_llm_agent_object(agent_name=agent_name)
        agent.update_agent(agent_attributes=agent_attributes)
        return AgogeResponse(data=agent_attributes)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@llm_agent_router.delete("/{agent_name}")
def delete_agent(
    agent_name: str,
    current_user: AgogeUser = Depends(admin_required)
) -> AgogeResponse:
    try:
        agent = LLMAgentFactory.create_llm_agent_object(agent_name=agent_name)
        agent.delete_agent()
        return AgogeResponse(data={"detail": f"Agent '{agent_name}' deleted successfully"})
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@llm_agent_router.websocket("/{agent_name}/chat")
async def websocket_chat(
    agent_name: str,
    websocket: WebSocket,
    current_user: AgogeUser = Depends(websocket_admin_required)
):
    agent = LLMAgentFactory.create_llm_agent_object(agent_name=agent_name)
    await manager.connect(websocket)
    try:
        while True:
            # Receive a message from the client
            user_message = await websocket.receive_text()

            # Process and send the user's message to the assistant
            await agent.send_message(user_message, websocket)

            # Stream the response back to the client
            for chunk in await agent.stream_response(websocket):
                await manager.send_personal_message(chunk, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
