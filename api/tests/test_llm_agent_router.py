import pytest
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_create_agent():
    agent_data = {
        "id": "test_agent",
        "friendly_name": "Andrew Bomberger",
        "role": "Cybersecurity Supervisor",
        "industry": "Agricultural Sector",
        "education_level": "Master's Degree in Cybersecurity",
        "tone": "Professional and Supportive",
        "prior_experience": "10 years in cybersecurity, specializing in network defense",
        "technical_proficiency": "Expert in SIEM and IDS tools"
    }
    response = client.post("/llm-agents/", json=agent_data)
    assert response.status_code == 200
    assert response.json() == agent_data


def test_get_agent():
    agent_name = "test_agent"
    response = client.get(f"/llm-agents/{agent_name}")
    assert response.status_code == 200
    assert response.json()["id"] == agent_name

def test_put_agent():
    agent_name = "test_agent"
    agent_data = {
        "id": "test_agent",
        "friendly_name": "Andrew Bomberger, Jr.",
        "role": "Cybersecurity Supervisor",
        "industry": "Agricultural Sector",
        "education_level": "Master's Degree in Cybersecurity",
        "tone": "Professional and Supportive",
        "prior_experience": "10 years in cybersecurity, specializing in network defense",
        "technical_proficiency": "Expert in SIEM and IDS tools"
    }

    response = client.put(f"/llm-agents/{agent_name}", json=agent_data)

    assert response.status_code == 200
    assert response.json() == agent_data


@pytest.mark.asyncio
async def test_websocket_chat():
    agent_name = "test_agent"

    with client.websocket_connect(f"/llm-agents/{agent_name}/chat") as websocket:
        websocket.send_text("Hello")
        data = websocket.receive_text()
        assert data.startswith("Response from OpenAI:")

        # Streaming test example
        for _ in range(3):
            chunk = websocket.receive_text()
            assert chunk.startswith("Streamed chunk:")


def test_delete_agent():
    agent_name = "test_agent"

    response = client.delete(f"/llm-agents/{agent_name}")

    assert response.status_code == 200
