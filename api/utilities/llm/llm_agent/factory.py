from common.constants.enumerators import LLMAgentTypes
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from .llm_agent import LLMAgent
from .llm_openai_agent import LLMOpenAIAgent


class LLMAgentFactory:
    """
    A factory class responsible for creating instances of different DocumentDatabase subclasses
    based on the specified database type. This factory centralizes the logic for instantiating
    the appropriate database object, ensuring that only supported database types are created.

    Attributes:
        logger (Logger): An instance of the Logger configured for cloud functions, used to log
                         information about database creation operations.
        _database_classes (dict): A dictionary mapping each supported DatabaseTypes enum to its
                                  corresponding DocumentDatabase subclass.
    """
    logger = Logger(LoggerNames.API).logger

    _llm_agent_classes = {
        LLMAgentTypes.openai: LLMOpenAIAgent
    }

    @staticmethod
    def create_llm_agent_object(
        agent_name: str = None,
        llm_agent_type: LLMAgentTypes = LLMAgentTypes.openai,
        env_dict: dict = None
    ) -> LLMAgent:
        llm_agent_class = LLMAgentFactory._llm_agent_classes.get(llm_agent_type)
        if not llm_agent_class:
            raise ValueError(f"Unsupported database type: {llm_agent_class.value}")
        LLMAgentFactory.logger.debug(f"Creating LLMAgentInstance of type: {llm_agent_class.value}")
        return llm_agent_class(agent_name=agent_name, env_dict=env_dict)
