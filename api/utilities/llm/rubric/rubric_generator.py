import openai
import json
from pydantic import ValidationError

from common.exceptions import BadRequest, RateLimitExceeded, ServiceUnavailable
from common.models.agoge import RubricModel
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class RubricGenerator:
    def __init__(self, env_dict: dict) -> None:
        self.log_name = LoggerNames.API
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name,
            project_id=self.env.project,
        )
        if not (api_key := self.env.openai_api_key):
            raise ServiceUnavailable(
                message="Rubric generation is not configured. Ask an Agoge administrator to configure the OpenAI API key."
            )
        # Keep each deployment's credentials on its own client. A billing error
        # cannot be fixed by retrying the same generation request automatically.
        self.client = openai.OpenAI(api_key=api_key, max_retries=0, timeout=60.0)
        self.logger = Logger(self.log_name, class_name=self.__class__.__name__)

    def generate_rubric(
        self,
        rubric_params: dict
    ) -> dict:
        """
        Generate rubric based on specified parameters (template)
        :param rubric_params: A dictionary with keys:
            - total_points: The total points for the rubric.
            - levels: List of rubric levels (e.g., ["Exemplary", "Proficient", "Developing", "Unsatisfactory"]).
            - categories: List of rubric categories (e.g., ["Configuration", "Documentation", "Communication", "Problem-solving"]).
            - id: The unit ID used for the Firestore rubric document.
        :return: The generated rubric content as a structured JSON response.
        """
        for field in ("levels", "categories"):
            values = rubric_params.get(field)
            if not isinstance(values, list) or not values or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise BadRequest(message=f"Rubric '{field}' must be a non-empty list of names.")
        rubric_id = rubric_params.get("id")
        if not isinstance(rubric_id, str) or not rubric_id:
            raise BadRequest(message="A rubric ID is required.")
        total_points = rubric_params.get("total_points")
        if isinstance(total_points, bool) or not isinstance(total_points, (int, float)) or total_points <= 0:
            raise BadRequest(message="Rubric total points must be a positive number.")
        levels = rubric_params['levels']
        categories = rubric_params['categories']

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
                "description": "Generates a rubric with categories, criteria, and headers",
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
                    "required": ["categories", "criteria", "headers"],
                },
            }
        ]

        # Sending prompt and functions to interact with gpt.
        # Note: Some models don't support structure!
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                functions=functions,
                function_call={"name": "create_rubric"},
                response_format={"type": "json_object"}
            )
        except openai.APIError as e:
            code = getattr(e, "code", None)
            self.logger.warning(
                "OpenAI rubric generation request failed.",
                rubric_id=rubric_id,
                provider_code=code,
                provider_status=getattr(e, "status_code", None),
                provider_request_id=getattr(e, "request_id", None),
            )
            if code == "credit_balance_exhausted":
                message = (
                    "Rubric generation is unavailable because the OpenAI API account has no credits remaining. "
                    "Ask an Agoge administrator to add API credits or configure a funded OpenAI API key."
                )
            elif getattr(e, "type", None) == "insufficient_quota" or code in {
                "insufficient_quota", "billing_hard_limit_reached",
                "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
                "organization_usage_limit_exceeded",
            }:
                message = (
                    "Rubric generation is unavailable because the OpenAI API account has exhausted its credits "
                    "or reached a usage limit. Ask an Agoge administrator to check API billing and usage limits."
                )
            elif isinstance(e, openai.RateLimitError):
                raise RateLimitExceeded(
                    message="Rubric generation is temporarily rate limited. Please wait a moment and try again."
                ) from e
            elif isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError)):
                message = (
                    "Rubric generation is unavailable because the OpenAI API credentials could not be authorized. "
                    "Ask an Agoge administrator to check the configured API key and its permissions."
                )
            else:
                message = "The AI service could not generate the rubric. Please try again later."
            raise ServiceUnavailable(message=message) from e

        # Validate the complete result before writing so a failed generation
        # cannot erase an existing rubric or leave an unusable document behind.
        try:
            message = response.choices[0].message
            arguments = json.loads(message.function_call.arguments)
            rubric = RubricModel(
                build_id=rubric_id,
                categories=arguments['categories'],
                criteria=arguments['criteria'],
                headers=arguments['headers'],
            )
            expected_cells = {(category, index) for category in categories for index in range(len(levels))}
            actual_cells = {(criterion.category, criterion.index) for criterion in rubric.criteria}
            if (
                rubric.categories != categories or len(rubric.headers) != len(levels)
                or actual_cells != expected_cells or len(rubric.criteria) != len(expected_cells)
            ):
                raise ValueError("Incomplete rubric returned by the AI service.")
        except (AttributeError, IndexError, KeyError, TypeError, ValueError, ValidationError) as e:
            self.logger.warning("OpenAI returned an invalid rubric.", rubric_id=rubric_id)
            raise ServiceUnavailable(
                message="The AI service returned an incomplete or invalid rubric. Please try generating it again."
            ) from e

        self.store_rubric(rubric)
        return rubric.model_dump()

    def store_rubric(
        self,
        rubric: RubricModel,
    ) -> None:
        """Store a validated rubric after generation completes successfully."""
        self.db.update(
            collection_name=DbCollections.RUBRIC,
            doc_id=rubric.build_id,
            data=rubric.model_dump()
        )
