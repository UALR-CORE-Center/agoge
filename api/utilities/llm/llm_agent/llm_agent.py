from abc import ABC, abstractmethod
from fastapi import WebSocket

from common.models.competency_assessment_agent import AgentAttributes, AgentConversationAttributes
from common.document_database.factory import DocumentDatabaseFactory
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class LLMAgent(ABC):
    """
    Abstract Base Class for an LLM Agent.

    This class defines the general methods and properties that every LLM agent should implement.
    It provides methods to create, delete, update, and load agents from the Firestore database.
    """
    DEFAULT_INSTRUCTIONS = """
    - Do not provide unsolicited help, advice, or guidance unless directly asked by the user.
    - Focus on responding to the user's input with follow-up questions or comments that simulate a 
      realistic work conversation.
    - Avoid taking initiative to assist unless explicitly requested by the learner.
    - Keep responses neutral and aligned with the user's context, maintaining a professional tone.
    - Act as a supervisor assessing and interacting, not as a helper or tutor.
    """
    ASSISTANT_MESSAGE = """
    You are an evaluator. You should only ask questions or prompt reflections. Avoid giving advice or instructions 
    unless explicitly asked.
    """

    def __init__(
        self,
        agent_name: str = None,
        env_dict: dict = None
    ) -> None:
        """
        Initialize the LLM Agent with the given agent name and environment configuration.

        Args:
            agent_name (str, optional): The name of the agent.
            env_dict (dict, optional): Environment variables or configurations.
        """
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict) if env_dict else CloudEnv(log_name=self.log_name)
        self.agent_name = agent_name
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )

    @abstractmethod
    def _create_or_update_llm_agent(self, agent_attributes: AgentAttributes):
        pass

    @abstractmethod
    def _load_llm_agent(self, agent_conversation_attributes: AgentConversationAttributes):
        """
        Abstract method for loading an agent in the LLM system.

        This method should be implemented by subclasses to handle the creation of the agent
        in the specific LLM system (e.g., OpenAI, Azure OpenAI).
        """
        pass

    @abstractmethod
    def _delete_llm_agent(self):
        """
        Abstract method for deleting an agent in the LLM system.

        This method should be implemented by subclasses to handle the deletion of the agent
        from the specific LLM system.
        """
        pass

    @abstractmethod
    def _update_llm_agent(self, **kwargs):
        """
        Abstract method for updating an agent in the LLM system.

        This method should be implemented by subclasses to handle the update of the agent
        in the specific LLM system.

        Args:
            **kwargs: Updated features or configurations for the agent.
        """
        pass

    @abstractmethod
    async def send_message(self, user_message: str, websocket: WebSocket):
        """
        Abstract method to send a message to the agent and receive a response.

        Args:
            user_message (str): The message from the user.

        Returns:
            str: The agent's response.
        """
        pass

    @abstractmethod
    async def stream_response(self, websocket: WebSocket):
        """
        Abstract method to stream the agent's response.

        This method should be implemented to yield response chunks from the agent.
        """
        pass

    def get_agent(self, agent_id: str) -> AgentAttributes:
        data = self.db.get(collection_name=DbCollections.LLM_AGENT, doc_id=self.agent_name)
        if data is None:
            self.logger.error(f"No agent found with ID {agent_id}", agent_id=self.agent_name)
            raise
        agent_attributes = AgentAttributes(**data)
        return agent_attributes

    def create_agent(self, agent_attributes: AgentAttributes):
        """
        Create a new LLM agent and store its attributes in Firestore. This function should be called when
        creating a new agent.

        Args:
            agent_attributes (AgentAttributes): The data required to create the agent.

        Raises:
            Exception: If agent creation fails.
        """
        if agent_attributes.id != self.agent_name:
            raise ValueError(
                f"Mismatch between agent IDs: the provided agent ID ({agent_attributes.id}) does not match the "
                f"expected ID ({self.agent_name}) used to instantiate this object."
            )

        try:
            self._create_or_update_llm_agent(agent_attributes=agent_attributes)

            # Save agent attributes to Firestore
            self.db.insert(collection_name=DbCollections.LLM_AGENT, data=agent_attributes.dict())
            self.logger.info(f"Agent '{self.agent_name}' created successfully.", agent_id=self.agent_name)
        except Exception as e:
            self.logger.error(
                f"Error occurred while creating LLM agent: {e}",
                agent_id=self.agent_name
            )
            raise

    def delete_agent(self):
        """
        Delete an existing LLM agent from Firestore and the LLM system.

        Raises:
            Exception: If agent deletion fails.
        """
        try:
            # Delete the agent from the LLM system
            self._delete_llm_agent()

            # Remove agent attributes from Firestore
            self.db.delete(
                collection_name=DbCollections.LLM_AGENT,
                doc_id=self.agent_name
            )
            self.logger.info(
                f"Agent '{self.agent_name}' deleted successfully.",
                agent_id=self.agent_name
            )
        except Exception as e:
            self.logger.error(
                f"Error occurred while deleting LLM agent: {e}",
                agent_id=self.agent_name
            )
            raise

    def update_agent(self, agent_attributes: AgentAttributes):
        """
        Update an existing LLM agent's attributes in Firestore and the LLM system.

        Args:
            data (dict): Updated attributes or configurations for the agent.

        Raises:
            Exception: If agent update fails.
        """
        try:
            # Update the agent in the LLM system
            self._create_or_update_llm_agent(agent_attributes)

            # Update agent attributes in Firestore
            self.db.update(
                collection_name=DbCollections.LLM_AGENT,
                doc_id=self.agent_name,
                data=agent_attributes.model_dump()
            )
            self.logger.info(
                f"Agent '{self.agent_name}' updated successfully.",
                agent_id=self.agent_name
            )
        except Exception as e:
            self.logger.error(
                f"Error occurred while updating LLM agent: {e}",
                agent_id=self.agent_name
            )
            raise

    def load_agent_in_llm(self, agent_conversation_attributes: AgentConversationAttributes):
        """
        Load an agent's attributes from Firestore.

        Raises:
            Exception: If agent loading fails.
        """
        try:
            # Fetch agent attributes from Firestore
            self.agent_attributes = self.db.get(
                collection_name=DbCollections.LLM_AGENT,
                doc_id=self.agent_name
            )
            if not self.agent_attributes:
                raise ValueError(f"Agent '{self.agent_name}' does not exist in the database.")

            # TODO: Need to better figure out how to handle this function
            self._load_llm_agent(agent_conversation_attributes)
            self.logger.info(
                f"Agent '{self.agent_name}' loaded successfully.",
                agent_id=self.agent_name
            )
        except Exception as e:
            self.logger.error(
                f"Error occurred while loading LLM agent: {e}",
                agent_id=self.agent_name
            )
            raise
