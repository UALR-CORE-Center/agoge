from openai import OpenAI, AssistantEventHandler
from fastapi import WebSocket

from common.models.competency_assessment_agent import AgentAttributes, AgentConversationAttributes

from .llm_agent import LLMAgent


class LLMOpenAIAgent(LLMAgent):
    """
    LLM Agent implementation for OpenAI models.

    This class provides methods to create, manage, and interact with an OpenAI assistant agent,
    including starting a conversation, handling messages, and streaming assistant responses.

    Attributes:
        client (OpenAI): The OpenAI client instance.
        assistant: The assistant agent instance created in OpenAI.
        thread: The conversation thread instance.
        conversation (list): A list to store the conversation history.
    """
    MODEL_NAME = "gpt-4o"

    class EventHandler(AssistantEventHandler):
        """
        Event handler for handling assistant events during streaming.

        Attributes:
            current_response (list): List to accumulate response chunks from the assistant.
        """

        def __init__(self):
            """
            Initialize the EventHandler.
            """
            super().__init__()
            self.current_response = []

        def on_text_created(self, text) -> None:
            """
            Called when text is created by the assistant.

            Args:
                text (str): The text created by the assistant.
            """
            print(f"\nassistant > ", end="", flush=True)

        def on_text_delta(self, delta, snapshot):
            """
            Called when a delta (partial response) is received from the assistant.

            Args:
                delta: The delta response object containing the new text.
                snapshot: The current state snapshot.
            """
            print(delta.value, end="", flush=True)
            self.current_response.append(delta.value)

        def finalize_response(self):
            """
            Finalize and return the full response from the assistant.

            Returns:
                str: The full assistant response.
            """
            full_response = ''.join(self.current_response).strip()
            self.current_response.clear()
            return full_response

    def __init__(self, agent_name: str, env_dict: dict = None):
        """
        Initialize the LLMOpenAIAgent.

        Args:
            agent_name (str): The name of the agent.
            env_dict (dict, optional): Environment variables or configurations.
        """
        super().__init__(agent_name, env_dict)

        try:
            self.client = OpenAI(api_key=self.env.openai_api_key)
            self.logger.info("OpenAI client initialized.")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client {self.agent_name}: {e}", agent_id=self.agent_name)
            raise

    def _create_or_update_llm_agent(self, agent_attributes: AgentAttributes):
        """
        Create an assistant in the OpenAI system.
        """
        # Check and delete existing assistant if necessary
        try:
            existing_assistants = self.client.beta.assistants.list()
            for existing_assistant in existing_assistants:
                if existing_assistant.name == self.agent_name:
                    self.logger.info(f"Assistant '{self.agent_name}' already exists. Deleting it.",
                                     agent_id=self.agent_name)
                    self.client.beta.assistants.delete(existing_assistant.id)
                    self.logger.info(f"Assistant '{self.agent_name}' has been deleted.", agent_id=self.agent_name)
                    break
        except Exception as e:
            self.logger.error(f"Failed to list or delete existing assistant for agent '{self.agent_name}': {e}",
                              agent_id=self.agent_name)
            raise

        # Create the new assistant with the work role specifications
        name = agent_attributes.friendly_name or agent_attributes.id
        instructions = f"""
            You are {name}. {self.ASSISTANT_MESSAGE}. Role: {agent_attributes.role}
            
            Key Instructions:
            {self.DEFAULT_INSTRUCTIONS}
            
            Identity and Assistant Attributes (as a JSON string):
            {agent_attributes.dict()}
        """
        try:
            self.assistant = self.client.beta.assistants.create(
                name=self.agent_name,
                instructions=instructions,
                tools=[],
                model=self.MODEL_NAME,
            )
            self.logger.info(f"Assistant '{self.agent_name}' created successfully.")
        except Exception as e:
            self.logger.error(f"Failed to create assistant '{self.agent_name}': {e}", agent_id=self.agent_name)
            raise

    def _load_llm_agent(self, agent_conversation_attributes: AgentConversationAttributes):
        # Create a thread for the conversation
        try:
            self.thread = self.client.beta.threads.create()
        except Exception as e:
            self.logger.error(f"Failed to create conversation thread for {self.agent_name}: {e}",
                              agent_id=self.agent_name)
            raise

        # Initialize list to capture conversation
        self.conversation = []

        """
        Start a conversation with the assistant.
        """
        initial_message = f"""
            Assistant Attributes for this Conversation (as a JSON string):
            {agent_conversation_attributes.dict()}        
        """
        # Start the conversation with initial assistant message
        try:
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="assistant",
                content=initial_message
            )
            self.logger.debug(f"Initial assistant message sent for agent {self.agent_name}.", agent_id=self.agent_name)
        except Exception as e:
            self.logger.error(f"Failed to send initial assistant message for agent '{self.agent_name}': {e}",
                              agent_id=self.agent_name)
            raise

    def _delete_llm_agent(self):
        """
        Delete an assistant in the OpenAI system.

        Raises:
            NotImplementedError: Method not yet implemented.
        """
        try:
            self.client.beta.assistants.delete(assistant_id=self.agent_name)
        except Exception as e:
            self.logger.error(f"Failed to delete agent '{self.agent_name}': {e}", agent_id=self.agent_name)
            raise

    def _update_llm_agent(self):
        """
        Update an assistant in the OpenAI system.

        Raises:
            NotImplementedError: Method not yet implemented.
        """
        raise NotImplementedError("Method _update_llm_agent is not yet implemented.")

    async def send_message(self, user_message: str, websocket: WebSocket):
        """
        Send a message from the user to the assistant and append it to the conversation.
        """
        self.conversation.append(("User", user_message))

        # Send user's message to the assistant
        try:
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=user_message
            )
            await websocket.send_text("User message sent to assistant.")
            self.logger.debug("User message sent to assistant.")
        except Exception as e:
            error_message = f"Failed to send user message: {e}"
            await websocket.send_text(error_message)
            self.logger.error(error_message)

    async def stream_response(self, websocket: WebSocket):
        """
        Stream the assistant's response back to the user through the WebSocket.
        """
        try:
            # Create an event handler instance
            handler = self.EventHandler()

            # Stream the assistant's response
            try:
                with self.client.beta.threads.runs.stream(
                        thread_id=self.thread.id,
                        assistant_id=self.assistant.id,
                        instructions=self.ASSISTANT_MESSAGE,
                        event_handler=handler,
                ) as stream:
                    stream.until_done()
                self.logger.debug("Assistant response received.")
            except Exception as e:
                error_message = f"Failed to stream assistant's response: {e}"
                await websocket.send_text(error_message)
                self.logger.error(error_message)
                return

            # Send each chunk of text as it's generated to the WebSocket
            for chunk in handler.current_response:
                await websocket.send_text(chunk)

            # Finalize and send the complete response once streaming is done
            full_response = handler.finalize_response()
            await websocket.send_text(full_response)
            self.conversation.append(("Assistant", full_response))
        except Exception as e:
            error_message = f"Error during response streaming: {e}"
            await websocket.send_text(error_message)
            self.logger.error(error_message)
