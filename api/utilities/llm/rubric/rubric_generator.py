import openai
import json
from typing import Union, List

from common.exceptions import ServiceUnavailable
from common.models.agoge import RubricModel
from common.constants.database import DATABASE_NAME, DatabaseTypes
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.rubric import Rubric


class RubricGenerator:
    def __init__(self, env_dict: dict) -> None:
        self.log_name = LoggerNames.API
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        if not (api_key := self.env.openai_api_key):
            raise ServiceUnavailable(message="OpenAI service not available.")
        openai.api_key = api_key
        self.rubric_handler = Rubric(env_dict=env_dict)
        self.logger = Logger(self.log_name, class_name=self.__class__.__name__)

    def generate_rubric(
        self,
        rubric_params: dict
    ) -> Union[dict, None]:
        """
        Generate rubric based on specified parameters (template)
        :param rubric_params: A dictionary with keys:
            - total_points: The total points for the rubric.
            - levels: List of rubric levels (e.g., ["Exemplary", "Proficient", "Developing", "Unsatisfactory"]).
            - categories: List of rubric categories (e.g., ["Configuration", "Documentation", "Communication", "Problem-solving"]).
            - name: Optional name of the rubric to be used as a key in Datastore.
        :return: The generated rubric content as a structured JSON response.
        """
        levels = rubric_params['levels']
        categories = rubric_params['categories']
        total_points = rubric_params['total_points']

        # Prompt that is used with the function later on. This is the simplest prompt I could make while it still worked
        prompt = (
            f"Create a rubric for an assignment totaling {total_points} points. "
            f"Use the following levels, ordered from highest to lowest: {', '.join(levels)}. "
            f"Categories: {', '.join(categories)}. Provide structured point ranges and descriptions for each level in each category.\n\n"
            "Please present the rubric in the following exact format:\n\n"
            "{\n"
            "  \"categories\": [...array of category names...],\n"
            "  \"criteria\": [\n"
            "    {\n"
            "      \"description\": \"...\",\n"
            "      \"point_range\": \"...\",\n"
            "      \"index\": \"...\","
            "      \"level_name\": \"...\",\n"
            "      \"category\": \"...\"\n"
            "    },\n"
            "    ... additional criteria objects ...\n"
            "  ],\n"
            "  \"headers\": [...array of headers for each level...]\n"
            "}\n\n"
            "Here is an example criterion object:\n\n"
            "{\n"
            "  \"description\": \"Exceptionally complete and precise configuration, adhering to all requirements. Clear evidence of comprehensive understanding is exhibited.\",\n"
            "  \"point_range\": \"23-25 points\",\n"
            "  \"index\": \"0\",\n"
            "  \"level_name\": \"Exemplary\",\n"
            "  \"category\": \"Configuration\"\n"
            "}\n\n"
            "Ensure that each category starts with index 0 and that levels are ordered from highest to lowest within each category. Use the same point ranges for levels across categories, as shown in the example and as JSON."
        )

        # This is the structure it uses when generating the rubric
        functions = [
            {
                "name": "create_rubric",
                "description": "Generates a rubric with build_id, categories, criteria, and headers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "criteria": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "point_range": {"type": "string"},
                                    "index": {"type": "string"},
                                    "level_name": {"type": "string"},
                                    "category": {"type": "string"},
                                },
                                "required": ["description", "point_range", "index", "level_name", "category"],
                            },
                        },
                        "headers": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                    },
                    "required": ["build_id", "categories", "criteria", "headers"],
                },
            }
        ]

        # Sending prompt and functions to interact with gpt.
        # Note: Some models don't support structure!
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            functions=functions,
            function_call={"name": "create_rubric"},
            response_format={"type": "json_object"}
        )

        # Extracts message object from the response and checks if it has a function call with args
        try:
            if isinstance(response.choices, list) and response.choices:
                message = response.choices[0].message
                if message.function_call and message.function_call.arguments:
                    arguments = json.loads(message.function_call.arguments)
                    rubric_content = arguments
                else:
                    self.logger.warning("Function call or arguments missing in message.")
                    rubric_content = None
            else:
                self.logger.error("Response choices are either not a list or empty", choices=response.choices)
                rubric_content = None
        except (AttributeError, IndexError, ValueError) as e:
            self.logger.error(f"Error processing response choices: {e}")
            rubric_content = None

        rubric_id = rubric_params.get("id")

        self.store_rubric(
            rubric_id=rubric_id,
            rubric_content=rubric_content['criteria'],
            categories=rubric_params['categories'],
            headers=rubric_params.get('headers', [])
        )

        return rubric_content

    def store_rubric(
        self,
        rubric_id: str,
        rubric_content: str,
        categories: List[str],
        headers: List[str]
    ) -> None:
        """
        Store the generated rubric in a document database.

        :param rubric_id: The unique identifier to store the rubric.
        :param rubric_content: The generated rubric content as an array of dictionaries.
        :param categories: List of rubric categories.
        :param headers: List of headers for each performance level.
        """
        rubric = RubricModel(
            build_id=rubric_id,
            criteria=rubric_content,
            categories=categories,
            headers=headers,
        )

        self.db.update(
            collection_name=self.rubric_handler.collection,
            doc_id=rubric_id,
            data=rubric.model_dump()
        )
