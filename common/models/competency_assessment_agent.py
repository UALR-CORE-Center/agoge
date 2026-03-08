from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    HttpUrl,
    field_validator
)
from typing import List, Optional, Union
from datetime import datetime
import uuid


class AgentAttributes(BaseModel):
    id: str = Field(..., description="The unique name for this agent.")
    friendly_name: str = Field(..., description="Name of the AI agent.")
    role: str = Field(..., description="The job position or role the agent is simulating "
                                       "(e.g., Cybersecurity Supervisor).")
    industry: str = Field(..., description="The industry relevant to the scenario (e.g., Agricultural Sector).")
    education_level: str = Field(..., description="The agent's educational background "
                                                  "(e.g., Master's Degree in Cybersecurity).")
    tone: str = Field(..., description="The tone the agent should maintain during the interaction "
                                       "(e.g., Professional and Supportive).")
    prior_experience: str = Field(..., description="The prior professional experience of the agent "
                                                   "(e.g., 10 years in cybersecurity, specializing in network "
                                                   "defense).")
    technical_proficiency: str = Field(..., description="The agent's level of technical skill or proficiency "
                                                        "(e.g., Expert in SIEM and IDS tools).")


class AgentConversationAttributes(BaseModel):
    relationship_to_learner: str = Field(..., description="Defines the relationship of the agent to the learner "
                                                          "(e.g., Direct Supervisor).")
    expected_conversation_time: str = Field(..., description="The expected duration for the conversation "
                                                             "(e.g., 15 minutes).")
    conversation_objective: str = Field(..., description="The goal or objective of the conversation "
                                                         "(e.g., Assess understanding of network security protocols).")
    task: str = Field(..., description="The specific task assigned to the agent for the interaction "
                                       "(e.g., Focus on network security and threat mitigation strategies).")

    feedback_preference: str = Field(..., description="How the agent prefers to give feedback "
                                                      "(e.g., Constructive with actionable insights).")
    assistant_limitations: Optional[str] = Field(None, description="Any limitations for the agent, such as restricted "
                                                                   "topics (e.g., Cannot discuss classified company "
                                                                   "projects).")
    assessment_criteria: str = Field(..., description="The criteria used by the agent to assess the learner’s "
                                                      "performance (e.g., Learner identifies multiple effective "
                                                      "network security controls).")
    learner_task: str = \
        Field(..., description="The task the learner is asked to complete (e.g., Explain how to secure a network "
                               "against a recent cyber threat).")
    learner_language_proficiency: str = Field(..., description="The learner's level of language proficiency "
                                                       "(e.g., Advanced English speaker).")
    learner_accessibility_needs: Optional[str] = Field(None, description="Any special accessibility requirements the "
                                                                         "learner may have (e.g., None).")


class CompetencyAssessmentAgent(BaseModel):
    agent: AgentAttributes = Field(..., description="Attributes specific to the competency agent, including role, "
                                                    "experience, and conversation details.")
    agent_conversation: AgentConversationAttributes = \
        Field(..., description="Attributes specific to the learner interacting with the agent.")
    rubric_criteria: str = Field(..., description="The rubric used to assess the learner’s performance during the "
                                                  "interaction.")
    submission_file: Optional[str] = Field(None, description="The file or report submitted by the learner for "
                                                             "assessment.")
    ai_assessment_results: Optional[str] = Field(None, description="The AI-generated assessment of the learner’s work, "
                                                                   "based on the rubric.")
    instructor_feedback: Optional[str] = Field(None, description="Feedback provided by the instructor after reviewing "
                                                                 "the AI-generated assessment.")
    conversation_transcript: Optional[str] = Field(None, description="The conversation history between the learner and "
                                                                     "the agent, for review.")
