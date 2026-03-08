# Agoge Pydantic Model Reference

_Auto-generated reference for core nested pydantic models in Agoge._

## Overview
This file contains auto-generated descriptions and schemas for two core Agoge models: Catalog and Unit.
* Catalog defines the blueprint for a lab, capturing all objects an administrator or instructor configures when designing a lab.
* Unit is a deployed instance of a Catalog created by a trainer for a specific class. Trainees launch their labs from these Units, with each lab being an isolated copy of the Unit specification built in the cloud.

In short, Catalogs determine what labs can be created, Units represent the labs prepared for students, and each student lab is a cloud-based instantiation of a Unit.

## `CatalogModel`

**Qualified name:** `common.models.agoge.CatalogModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `discriminator` | `str` | ✔️ | — | Discriminator field |
| `networks` | `typing.Optional` | — | — |  |
| `servers` | `typing.Optional` | — | — |  |
| `summary` | `AgogeSummaryModel` | ✔️ | — |  |
| `firewall_rules` | `typing.Optional` | — | — |  |
| `instructor_id` | `typing.Union` | ✔️ | — | List of instructor IDs |
| `creation_timestamp` | `typing.Optional` | — | — |  |
| `build_type` | `str` | ✔️ | — | Build type of the unit |
| `version` | `str` | ✔️ | — | Version of the unit |
| `id` | `str` | ✔️ | — | ID of the unit |
| `assessment` | `typing.Optional` | — | — | Use Agoge to provide grading support |
| `lms_quiz` | `typing.Optional` | — | — | Use connected LMS to provide grading support and distribution functionality |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "AgogeSummaryModel": {
      "properties": {
        "name": {
          "description": "Name of the Agoge summary",
          "title": "Name",
          "type": "string"
        },
        "description": {
          "description": "Description of the Agoge summary",
          "title": "Description",
          "type": "string"
        },
        "teacher_instructions_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "URL for teacher instructions",
          "title": "Teacher Instructions Url"
        },
        "student_instructions_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "URL for student instructions",
          "title": "Student Instructions Url"
        },
        "hourly_cost": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Hourly cost of the Agoge summary",
          "title": "Hourly Cost"
        },
        "author": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Author of the Agoge summary",
          "title": "Author"
        },
        "standard_mappings": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/StandardMappingsModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Curriculum standard mappings for this lab",
          "title": "Standard Mappings"
        },
        "tags": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/TeachingConceptsModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "description": "Key concepts that this build is intended to teach",
          "title": "Tags"
        }
      },
      "required": [
        "name",
        "description"
      ],
      "title": "AgogeSummaryModel",
      "type": "object"
    },
    "AssessmentModel": {
      "properties": {
        "questions": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/AssessmentQuestionModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Questions"
        },
        "assessment_script": {
          "anyOf": [
            {
              "$ref": "#/$defs/AssessmentScriptModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The assessment script for all indicated questions."
        },
        "key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Key used for decrypting workout secrets in container applications",
          "title": "Key"
        }
      },
      "title": "AssessmentModel",
      "type": "object"
    },
    "AssessmentQuestionModel": {
      "properties": {
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "An ID to use when referring to specific questions",
          "title": "Id"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The name of the question, which is also used for the workout-level assessment script.",
          "title": "Name"
        },
        "type": {
          "description": "Type of the question",
          "title": "Type",
          "type": "string"
        },
        "question": {
          "description": "Question text",
          "title": "Question",
          "type": "string"
        },
        "key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The value used for decrypting individual cryptographic questions",
          "title": "Key"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The answer to the question for questions of type input",
          "title": "Answer"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Complete"
        }
      },
      "required": [
        "type",
        "question"
      ],
      "title": "AssessmentQuestionModel",
      "type": "object"
    },
    "AssessmentScriptModel": {
      "properties": {
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        }
      },
      "title": "AssessmentScriptModel",
      "type": "object"
    },
    "FirewallRuleModel": {
      "properties": {
        "name": {
          "description": "Name of the firewall rule",
          "title": "Name",
          "type": "string"
        },
        "network": {
          "description": "Network of the firewall rule",
          "title": "Network",
          "type": "string"
        },
        "action": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Action of the firewall rule",
          "title": "Action"
        },
        "target_tags": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "title": "Target Tags"
        },
        "protocol": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Protocol of the firewall rule",
          "title": "Protocol"
        },
        "ports": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of ports to apply rule to.",
          "title": "Ports"
        },
        "ip_ranges": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": [
            "0.0.0.0/0"
          ],
          "description": "Range of source or destination IPs to attach rule to.",
          "title": "Ip Ranges"
        },
        "direction": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "INGRESS",
          "description": "Direction of flow of traffic.",
          "title": "Direction"
        },
        "priority": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 1000,
          "description": "Rule priority.",
          "title": "Priority"
        }
      },
      "required": [
        "name",
        "network"
      ],
      "title": "FirewallRuleModel",
      "type": "object"
    },
    "HumanInteractionModel": {
      "properties": {
        "display": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Display"
        },
        "protocol": {
          "description": "Protocol of the human interaction",
          "title": "Protocol",
          "type": "string"
        },
        "username": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Username"
        },
        "password": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Password"
        },
        "ssh_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ssh Key"
        },
        "domain": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Domain"
        },
        "security_mode": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "nla",
          "description": "Security mode of the human interaction",
          "title": "Security Mode"
        }
      },
      "required": [
        "protocol"
      ],
      "title": "HumanInteractionModel",
      "type": "object"
    },
    "LMSConnectionModel": {
      "properties": {
        "lms_type": {
          "description": "The type of LMS this should integrate with.",
          "title": "Lms Type",
          "type": "string"
        },
        "api_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The API key from the user profile needed for connecting to the LMS",
          "title": "Api Key"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The LMS API URL",
          "title": "Url"
        },
        "course_code": {
          "description": "The course code to use for creating the LMS assignments",
          "title": "Course Code",
          "type": "integer"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Name of LMS course",
          "title": "Name"
        }
      },
      "required": [
        "lms_type",
        "course_code"
      ],
      "title": "LMSConnectionModel",
      "type": "object"
    },
    "LMSIntegrationModel": {
      "properties": {
        "lms_connection": {
          "anyOf": [
            {
              "$ref": "#/$defs/LMSConnectionModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The information needed to connect a lab to a course"
        },
        "course_work": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "assignment",
          "description": "Practice quiz or assignment",
          "title": "Course Work"
        },
        "due_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Due date for assignment",
          "title": "Due At"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Description of assignment",
          "title": "Description"
        },
        "allowed_attempts": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": -1.0,
          "description": "Attempts available for assignment, -1 is unlimited",
          "title": "Allowed Attempts"
        },
        "assessment_script": {
          "anyOf": [
            {
              "$ref": "#/$defs/AssessmentScriptModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The assessment script for all indicated questions."
        },
        "questions": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/LMSQuizQuestionsModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Questions"
        }
      },
      "title": "LMSIntegrationModel",
      "type": "object"
    },
    "LMSQuizAnswerModel": {
      "properties": {
        "answer_text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Answer text",
          "title": "Answer Text"
        },
        "weight": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": 0.0,
          "description": "Weight of the answer",
          "title": "Weight"
        }
      },
      "title": "LMSQuizAnswerModel",
      "type": "object"
    },
    "LMSQuizQuestionsModel": {
      "properties": {
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question name",
          "title": "Name"
        },
        "question_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Alternative field for question name (Canvas specific).",
          "title": "Question Name"
        },
        "question_text": {
          "description": "Question text",
          "title": "Question Text",
          "type": "string"
        },
        "question_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question type",
          "title": "Question Type"
        },
        "points_possible": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Points possible",
          "title": "Points Possible"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "bonus": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Whether to count this question as a bonus",
          "title": "Bonus"
        },
        "answers": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/LMSQuizAnswerModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question answers",
          "title": "Answers"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Used to mark completion for multi-step auto assessment scripts",
          "title": "Complete"
        }
      },
      "required": [
        "question_text"
      ],
      "title": "LMSQuizQuestionsModel",
      "type": "object"
    },
    "NetworkModel": {
      "properties": {
        "name": {
          "description": "Name of the network",
          "title": "Name",
          "type": "string"
        },
        "subnets": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/SubNetworkModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Subnets"
        },
        "reservations": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reservations"
        }
      },
      "required": [
        "name"
      ],
      "title": "NetworkModel",
      "type": "object"
    },
    "NicModel": {
      "properties": {
        "network": {
          "description": "Network of the NIC",
          "title": "Network",
          "type": "string"
        },
        "internal_ip": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Internal IP of the NIC",
          "title": "Internal Ip"
        },
        "subnet_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "default",
          "description": "Subnet name of the NIC",
          "title": "Subnet Name"
        },
        "external_nat": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Must be true if servers on network are intended to communicate outside of network.",
          "title": "External Nat"
        },
        "ip_aliases": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Assign multiple IP values to NIC.",
          "title": "Ip Aliases"
        },
        "direct_connect": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Allow users to connect without using a proxy-machine.",
          "title": "Direct Connect"
        }
      },
      "required": [
        "network"
      ],
      "title": "NicModel",
      "type": "object"
    },
    "ServerDetailsModel": {
      "properties": {
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Useful services and programs this image is providing related to the workout.",
          "title": "Description"
        },
        "os": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Operating system of the server",
          "title": "Os"
        },
        "labels": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of services and functionality provided on this server.",
          "title": "Labels"
        }
      },
      "title": "ServerDetailsModel",
      "type": "object"
    },
    "ServerModel": {
      "description": "Servers used as part of a Unit or Unit Workout lab.\nPartially based on information stored in AgogeImageModel objects.",
      "properties": {
        "add_disk": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 0,
          "description": "Additional disk space of the server",
          "title": "Add Disk"
        },
        "build_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Build type of the server",
          "title": "Build Type"
        },
        "can_ip_forward": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether IP forwarding is enabled",
          "title": "Can Ip Forward"
        },
        "community_server": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether this server should be a shared server in a community build unit.",
          "title": "Community Server"
        },
        "details": {
          "anyOf": [
            {
              "$ref": "#/$defs/ServerDetailsModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "firewall_rules": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/FirewallRuleModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of firewall rules associated with server.",
          "title": "Firewall Rules"
        },
        "hidden": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether to display this server to students or not.",
          "title": "Hidden"
        },
        "human_interaction": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/HumanInteractionModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Human Interaction"
        },
        "hostname": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Public DNS record associated with server.",
          "title": "Hostname"
        },
        "image": {
          "description": "Image of the server",
          "title": "Image",
          "type": "string"
        },
        "machine_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "e1-standard1",
          "description": "Machine type of the server",
          "title": "Machine Type"
        },
        "metadata": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Metadata of the server",
          "title": "Metadata"
        },
        "guacamole_startup_script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Optional startup script for Guacamole service",
          "title": "Guacamole Startup Script"
        },
        "startup_scripts": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Optional startup scripts to pass into server",
          "title": "Startup Scripts"
        },
        "min_cpu_platform": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "",
          "description": "Minimum CPU platform of the server",
          "title": "Min Cpu Platform"
        },
        "name": {
          "description": "Name of server.",
          "title": "Name",
          "type": "string"
        },
        "nics": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/NicModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Nics"
        },
        "parent_build_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Build type of parent object (i.e. workout, unit, etc.).",
          "title": "Parent Build Type"
        },
        "parent_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "ID of parent object to associate with server.",
          "title": "Parent Id"
        },
        "shutoff_timestamp": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Timestamp of when server will shut down.",
          "title": "Shutoff Timestamp"
        },
        "sshkey": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "SSH key of the server",
          "title": "Sshkey"
        },
        "tags": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Optional field used for attaching specific firewall rules to machine",
          "title": "Tags"
        },
        "state": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Current build state of server",
          "title": "State"
        },
        "state_timestamp": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Timestamp of the server state",
          "title": "State Timestamp"
        }
      },
      "required": [
        "image",
        "name"
      ],
      "title": "ServerModel",
      "type": "object"
    },
    "StandardMappingsModel": {
      "properties": {
        "framework": {
          "description": "Framework of the standard mapping",
          "title": "Framework",
          "type": "string"
        },
        "mapping": {
          "description": "Mapping of the standard",
          "title": "Mapping",
          "type": "string"
        }
      },
      "required": [
        "framework",
        "mapping"
      ],
      "title": "StandardMappingsModel",
      "type": "object"
    },
    "SubNetworkModel": {
      "properties": {
        "name": {
          "description": "Name of the subnetwork",
          "title": "Name",
          "type": "string"
        },
        "ip_subnet": {
          "description": "IP subnet of the subnetwork",
          "title": "Ip Subnet",
          "type": "string"
        },
        "promiscuous_mode": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Toggle promiscuous mode for this subnetwork",
          "title": "Promiscuous Mode"
        }
      },
      "required": [
        "name",
        "ip_subnet"
      ],
      "title": "SubNetworkModel",
      "type": "object"
    },
    "TeachingConceptsModel": {
      "properties": {
        "id": {
          "description": "ID of the teaching concept",
          "title": "Id",
          "type": "string"
        },
        "name": {
          "description": "Name of the teaching concept",
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name"
      ],
      "title": "TeachingConceptsModel",
      "type": "object"
    }
  },
  "properties": {
    "discriminator": {
      "description": "Discriminator field",
      "title": "Discriminator",
      "type": "string"
    },
    "networks": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/NetworkModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Networks"
    },
    "servers": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/ServerModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Servers"
    },
    "summary": {
      "$ref": "#/$defs/AgogeSummaryModel"
    },
    "firewall_rules": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/FirewallRuleModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Firewall Rules"
    },
    "instructor_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      ],
      "description": "List of instructor IDs",
      "title": "Instructor Id"
    },
    "creation_timestamp": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Creation Timestamp"
    },
    "build_type": {
      "description": "Build type of the unit",
      "title": "Build Type",
      "type": "string"
    },
    "version": {
      "description": "Version of the unit",
      "title": "Version",
      "type": "string"
    },
    "id": {
      "description": "ID of the unit",
      "title": "Id",
      "type": "string"
    },
    "assessment": {
      "anyOf": [
        {
          "$ref": "#/$defs/AssessmentModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Use Agoge to provide grading support"
    },
    "lms_quiz": {
      "anyOf": [
        {
          "$ref": "#/$defs/LMSIntegrationModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Use connected LMS to provide grading support and distribution functionality"
    }
  },
  "required": [
    "discriminator",
    "summary",
    "instructor_id",
    "build_type",
    "version",
    "id"
  ],
  "title": "CatalogModel",
  "type": "object"
}
```
</details>

## `AgogeSummaryModel`

**Qualified name:** `common.models.agoge.AgogeSummaryModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the Agoge summary |
| `description` | `str` | ✔️ | — | Description of the Agoge summary |
| `teacher_instructions_url` | `typing.Optional` | — | — | URL for teacher instructions |
| `student_instructions_url` | `typing.Optional` | — | — | URL for student instructions |
| `hourly_cost` | `typing.Optional` | — | — | Hourly cost of the Agoge summary |
| `author` | `typing.Optional` | — | — | Author of the Agoge summary |
| `standard_mappings` | `typing.Optional` | — | — | Curriculum standard mappings for this lab |
| `tags` | `typing.Optional` | — | `PydanticUndefined` | Key concepts that this build is intended to teach |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "StandardMappingsModel": {
      "properties": {
        "framework": {
          "description": "Framework of the standard mapping",
          "title": "Framework",
          "type": "string"
        },
        "mapping": {
          "description": "Mapping of the standard",
          "title": "Mapping",
          "type": "string"
        }
      },
      "required": [
        "framework",
        "mapping"
      ],
      "title": "StandardMappingsModel",
      "type": "object"
    },
    "TeachingConceptsModel": {
      "properties": {
        "id": {
          "description": "ID of the teaching concept",
          "title": "Id",
          "type": "string"
        },
        "name": {
          "description": "Name of the teaching concept",
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name"
      ],
      "title": "TeachingConceptsModel",
      "type": "object"
    }
  },
  "properties": {
    "name": {
      "description": "Name of the Agoge summary",
      "title": "Name",
      "type": "string"
    },
    "description": {
      "description": "Description of the Agoge summary",
      "title": "Description",
      "type": "string"
    },
    "teacher_instructions_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "URL for teacher instructions",
      "title": "Teacher Instructions Url"
    },
    "student_instructions_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "URL for student instructions",
      "title": "Student Instructions Url"
    },
    "hourly_cost": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Hourly cost of the Agoge summary",
      "title": "Hourly Cost"
    },
    "author": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Author of the Agoge summary",
      "title": "Author"
    },
    "standard_mappings": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/StandardMappingsModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Curriculum standard mappings for this lab",
      "title": "Standard Mappings"
    },
    "tags": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/TeachingConceptsModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "description": "Key concepts that this build is intended to teach",
      "title": "Tags"
    }
  },
  "required": [
    "name",
    "description"
  ],
  "title": "AgogeSummaryModel",
  "type": "object"
}
```
</details>

## `AssessmentModel`

**Qualified name:** `common.models.agoge.AssessmentModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `questions` | `typing.Optional` | — | — |  |
| `assessment_script` | `typing.Optional` | — | — | The assessment script for all indicated questions. |
| `key` | `typing.Optional` | — | — | Key used for decrypting workout secrets in container applications |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "AssessmentQuestionModel": {
      "properties": {
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "An ID to use when referring to specific questions",
          "title": "Id"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The name of the question, which is also used for the workout-level assessment script.",
          "title": "Name"
        },
        "type": {
          "description": "Type of the question",
          "title": "Type",
          "type": "string"
        },
        "question": {
          "description": "Question text",
          "title": "Question",
          "type": "string"
        },
        "key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The value used for decrypting individual cryptographic questions",
          "title": "Key"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The answer to the question for questions of type input",
          "title": "Answer"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Complete"
        }
      },
      "required": [
        "type",
        "question"
      ],
      "title": "AssessmentQuestionModel",
      "type": "object"
    },
    "AssessmentScriptModel": {
      "properties": {
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        }
      },
      "title": "AssessmentScriptModel",
      "type": "object"
    }
  },
  "properties": {
    "questions": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/AssessmentQuestionModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Questions"
    },
    "assessment_script": {
      "anyOf": [
        {
          "$ref": "#/$defs/AssessmentScriptModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The assessment script for all indicated questions."
    },
    "key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Key used for decrypting workout secrets in container applications",
      "title": "Key"
    }
  },
  "title": "AssessmentModel",
  "type": "object"
}
```
</details>

## `AssessmentQuestionModel`

**Qualified name:** `common.models.agoge.AssessmentQuestionModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `id` | `typing.Optional` | — | `PydanticUndefined` | An ID to use when referring to specific questions |
| `name` | `typing.Optional` | — | — | The name of the question, which is also used for the workout-level assessment script. |
| `type` | `str` | ✔️ | — | Type of the question |
| `question` | `str` | ✔️ | — | Question text |
| `key` | `typing.Optional` | — | — | The value used for decrypting individual cryptographic questions |
| `answer` | `typing.Optional` | — | — | The answer to the question for questions of type input |
| `script_assessment` | `typing.Optional` | — | `False` |  |
| `complete` | `typing.Optional` | — | `False` |  |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "An ID to use when referring to specific questions",
      "title": "Id"
    },
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The name of the question, which is also used for the workout-level assessment script.",
      "title": "Name"
    },
    "type": {
      "description": "Type of the question",
      "title": "Type",
      "type": "string"
    },
    "question": {
      "description": "Question text",
      "title": "Question",
      "type": "string"
    },
    "key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The value used for decrypting individual cryptographic questions",
      "title": "Key"
    },
    "answer": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The answer to the question for questions of type input",
      "title": "Answer"
    },
    "script_assessment": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Script Assessment"
    },
    "complete": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Complete"
    }
  },
  "required": [
    "type",
    "question"
  ],
  "title": "AssessmentQuestionModel",
  "type": "object"
}
```
</details>

## `AssessmentScriptModel`

**Qualified name:** `common.models.agoge.AssessmentScriptModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `script` | `typing.Optional` | — | — | script name (e.g. attack.py) |
| `script_language` | `typing.Optional` | — | — | e.g. python |
| `server` | `typing.Optional` | — | — | Server that runs script. |
| `operating_system` | `typing.Optional` | — | — | Target server operating system |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "script": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "script name (e.g. attack.py)",
      "title": "Script"
    },
    "script_language": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "e.g. python",
      "title": "Script Language"
    },
    "server": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Server that runs script.",
      "title": "Server"
    },
    "operating_system": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Target server operating system",
      "title": "Operating System"
    }
  },
  "title": "AssessmentScriptModel",
  "type": "object"
}
```
</details>

## `FirewallRuleModel`

**Qualified name:** `common.models.agoge.FirewallRuleModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the firewall rule |
| `network` | `str` | ✔️ | — | Network of the firewall rule |
| `action` | `typing.Optional` | — | — | Action of the firewall rule |
| `target_tags` | `typing.Optional` | — | `PydanticUndefined` |  |
| `protocol` | `typing.Optional` | — | — | Protocol of the firewall rule |
| `ports` | `typing.Optional` | — | — | List of ports to apply rule to. |
| `ip_ranges` | `typing.Optional` | — | `['0.0.0.0/0']` | Range of source or destination IPs to attach rule to. |
| `direction` | `typing.Optional` | — | `INGRESS` | Direction of flow of traffic. |
| `priority` | `typing.Optional` | — | `1000` | Rule priority. |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "description": "Name of the firewall rule",
      "title": "Name",
      "type": "string"
    },
    "network": {
      "description": "Network of the firewall rule",
      "title": "Network",
      "type": "string"
    },
    "action": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Action of the firewall rule",
      "title": "Action"
    },
    "target_tags": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Target Tags"
    },
    "protocol": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Protocol of the firewall rule",
      "title": "Protocol"
    },
    "ports": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "List of ports to apply rule to.",
      "title": "Ports"
    },
    "ip_ranges": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": [
        "0.0.0.0/0"
      ],
      "description": "Range of source or destination IPs to attach rule to.",
      "title": "Ip Ranges"
    },
    "direction": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "INGRESS",
      "description": "Direction of flow of traffic.",
      "title": "Direction"
    },
    "priority": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": 1000,
      "description": "Rule priority.",
      "title": "Priority"
    }
  },
  "required": [
    "name",
    "network"
  ],
  "title": "FirewallRuleModel",
  "type": "object"
}
```
</details>

## `HumanInteractionModel`

**Qualified name:** `common.models.agoge.HumanInteractionModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `display` | `typing.Optional` | — | `False` |  |
| `protocol` | `str` | ✔️ | — | Protocol of the human interaction |
| `username` | `typing.Optional` | — | — |  |
| `password` | `typing.Optional` | — | — |  |
| `ssh_key` | `typing.Optional` | — | — |  |
| `domain` | `typing.Optional` | — | — |  |
| `security_mode` | `typing.Optional` | — | `SecurityModes.NLA` | Security mode of the human interaction |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "display": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Display"
    },
    "protocol": {
      "description": "Protocol of the human interaction",
      "title": "Protocol",
      "type": "string"
    },
    "username": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Username"
    },
    "password": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Password"
    },
    "ssh_key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Ssh Key"
    },
    "domain": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Domain"
    },
    "security_mode": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "nla",
      "description": "Security mode of the human interaction",
      "title": "Security Mode"
    }
  },
  "required": [
    "protocol"
  ],
  "title": "HumanInteractionModel",
  "type": "object"
}
```
</details>

## `LMSConnectionModel`

**Qualified name:** `common.models.agoge.LMSConnectionModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `lms_type` | `str` | ✔️ | — | The type of LMS this should integrate with. |
| `api_key` | `typing.Optional` | — | — | The API key from the user profile needed for connecting to the LMS |
| `url` | `typing.Optional` | — | — | The LMS API URL |
| `course_code` | `int` | ✔️ | — | The course code to use for creating the LMS assignments |
| `name` | `typing.Optional` | — | — | Name of LMS course |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "lms_type": {
      "description": "The type of LMS this should integrate with.",
      "title": "Lms Type",
      "type": "string"
    },
    "api_key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The API key from the user profile needed for connecting to the LMS",
      "title": "Api Key"
    },
    "url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The LMS API URL",
      "title": "Url"
    },
    "course_code": {
      "description": "The course code to use for creating the LMS assignments",
      "title": "Course Code",
      "type": "integer"
    },
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Name of LMS course",
      "title": "Name"
    }
  },
  "required": [
    "lms_type",
    "course_code"
  ],
  "title": "LMSConnectionModel",
  "type": "object"
}
```
</details>

## `LMSIntegrationModel`

**Qualified name:** `common.models.agoge.LMSIntegrationModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `lms_connection` | `typing.Optional` | — | — | The information needed to connect a lab to a course |
| `course_work` | `typing.Optional` | — | `assignment` | Practice quiz or assignment |
| `due_at` | `typing.Optional` | — | — | Due date for assignment |
| `description` | `typing.Optional` | — | — | Description of assignment |
| `allowed_attempts` | `typing.Optional` | — | `-1.0` | Attempts available for assignment, -1 is unlimited |
| `assessment_script` | `typing.Optional` | — | — | The assessment script for all indicated questions. |
| `questions` | `typing.Optional` | — | — |  |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "AssessmentScriptModel": {
      "properties": {
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        }
      },
      "title": "AssessmentScriptModel",
      "type": "object"
    },
    "LMSConnectionModel": {
      "properties": {
        "lms_type": {
          "description": "The type of LMS this should integrate with.",
          "title": "Lms Type",
          "type": "string"
        },
        "api_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The API key from the user profile needed for connecting to the LMS",
          "title": "Api Key"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The LMS API URL",
          "title": "Url"
        },
        "course_code": {
          "description": "The course code to use for creating the LMS assignments",
          "title": "Course Code",
          "type": "integer"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Name of LMS course",
          "title": "Name"
        }
      },
      "required": [
        "lms_type",
        "course_code"
      ],
      "title": "LMSConnectionModel",
      "type": "object"
    },
    "LMSQuizAnswerModel": {
      "properties": {
        "answer_text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Answer text",
          "title": "Answer Text"
        },
        "weight": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": 0.0,
          "description": "Weight of the answer",
          "title": "Weight"
        }
      },
      "title": "LMSQuizAnswerModel",
      "type": "object"
    },
    "LMSQuizQuestionsModel": {
      "properties": {
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question name",
          "title": "Name"
        },
        "question_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Alternative field for question name (Canvas specific).",
          "title": "Question Name"
        },
        "question_text": {
          "description": "Question text",
          "title": "Question Text",
          "type": "string"
        },
        "question_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question type",
          "title": "Question Type"
        },
        "points_possible": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Points possible",
          "title": "Points Possible"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "bonus": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Whether to count this question as a bonus",
          "title": "Bonus"
        },
        "answers": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/LMSQuizAnswerModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question answers",
          "title": "Answers"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Used to mark completion for multi-step auto assessment scripts",
          "title": "Complete"
        }
      },
      "required": [
        "question_text"
      ],
      "title": "LMSQuizQuestionsModel",
      "type": "object"
    }
  },
  "properties": {
    "lms_connection": {
      "anyOf": [
        {
          "$ref": "#/$defs/LMSConnectionModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The information needed to connect a lab to a course"
    },
    "course_work": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "assignment",
      "description": "Practice quiz or assignment",
      "title": "Course Work"
    },
    "due_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Due date for assignment",
      "title": "Due At"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Description of assignment",
      "title": "Description"
    },
    "allowed_attempts": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": -1.0,
      "description": "Attempts available for assignment, -1 is unlimited",
      "title": "Allowed Attempts"
    },
    "assessment_script": {
      "anyOf": [
        {
          "$ref": "#/$defs/AssessmentScriptModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The assessment script for all indicated questions."
    },
    "questions": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/LMSQuizQuestionsModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Questions"
    }
  },
  "title": "LMSIntegrationModel",
  "type": "object"
}
```
</details>

## `LMSQuizAnswerModel`

**Qualified name:** `common.models.agoge.LMSQuizAnswerModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `answer_text` | `typing.Optional` | — | — | Answer text |
| `weight` | `typing.Optional` | — | `0.0` | Weight of the answer |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "answer_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Answer text",
      "title": "Answer Text"
    },
    "weight": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": 0.0,
      "description": "Weight of the answer",
      "title": "Weight"
    }
  },
  "title": "LMSQuizAnswerModel",
  "type": "object"
}
```
</details>

## `LMSQuizQuestionsModel`

**Qualified name:** `common.models.agoge.LMSQuizQuestionsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `typing.Optional` | — | — | Question name |
| `question_name` | `typing.Optional` | — | — | Alternative field for question name (Canvas specific). |
| `question_text` | `str` | ✔️ | — | Question text |
| `question_type` | `typing.Optional` | — | — | Question type |
| `points_possible` | `typing.Optional` | — | — | Points possible |
| `script_assessment` | `typing.Optional` | — | `False` |  |
| `bonus` | `typing.Optional` | — | — | Whether to count this question as a bonus |
| `answers` | `typing.Optional` | — | — | Question answers |
| `complete` | `typing.Optional` | — | — | Used to mark completion for multi-step auto assessment scripts |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "LMSQuizAnswerModel": {
      "properties": {
        "answer_text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Answer text",
          "title": "Answer Text"
        },
        "weight": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": 0.0,
          "description": "Weight of the answer",
          "title": "Weight"
        }
      },
      "title": "LMSQuizAnswerModel",
      "type": "object"
    }
  },
  "properties": {
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Question name",
      "title": "Name"
    },
    "question_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Alternative field for question name (Canvas specific).",
      "title": "Question Name"
    },
    "question_text": {
      "description": "Question text",
      "title": "Question Text",
      "type": "string"
    },
    "question_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Question type",
      "title": "Question Type"
    },
    "points_possible": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Points possible",
      "title": "Points Possible"
    },
    "script_assessment": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Script Assessment"
    },
    "bonus": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Whether to count this question as a bonus",
      "title": "Bonus"
    },
    "answers": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/LMSQuizAnswerModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Question answers",
      "title": "Answers"
    },
    "complete": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Used to mark completion for multi-step auto assessment scripts",
      "title": "Complete"
    }
  },
  "required": [
    "question_text"
  ],
  "title": "LMSQuizQuestionsModel",
  "type": "object"
}
```
</details>

## `NetworkModel`

**Qualified name:** `common.models.agoge.NetworkModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the network |
| `subnets` | `typing.Optional` | — | — |  |
| `reservations` | `typing.Optional` | — | — |  |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "SubNetworkModel": {
      "properties": {
        "name": {
          "description": "Name of the subnetwork",
          "title": "Name",
          "type": "string"
        },
        "ip_subnet": {
          "description": "IP subnet of the subnetwork",
          "title": "Ip Subnet",
          "type": "string"
        },
        "promiscuous_mode": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Toggle promiscuous mode for this subnetwork",
          "title": "Promiscuous Mode"
        }
      },
      "required": [
        "name",
        "ip_subnet"
      ],
      "title": "SubNetworkModel",
      "type": "object"
    }
  },
  "properties": {
    "name": {
      "description": "Name of the network",
      "title": "Name",
      "type": "string"
    },
    "subnets": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/SubNetworkModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Subnets"
    },
    "reservations": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Reservations"
    }
  },
  "required": [
    "name"
  ],
  "title": "NetworkModel",
  "type": "object"
}
```
</details>

## `NicModel`

**Qualified name:** `common.models.agoge.NicModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `network` | `str` | ✔️ | — | Network of the NIC |
| `internal_ip` | `typing.Optional` | — | — | Internal IP of the NIC |
| `subnet_name` | `typing.Optional` | — | `default` | Subnet name of the NIC |
| `external_nat` | `typing.Optional` | — | `False` | Must be true if servers on network are intended to communicate outside of network. |
| `ip_aliases` | `typing.Optional` | — | — | Assign multiple IP values to NIC. |
| `direct_connect` | `typing.Optional` | — | `False` | Allow users to connect without using a proxy-machine. |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "network": {
      "description": "Network of the NIC",
      "title": "Network",
      "type": "string"
    },
    "internal_ip": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Internal IP of the NIC",
      "title": "Internal Ip"
    },
    "subnet_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "default",
      "description": "Subnet name of the NIC",
      "title": "Subnet Name"
    },
    "external_nat": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Must be true if servers on network are intended to communicate outside of network.",
      "title": "External Nat"
    },
    "ip_aliases": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Assign multiple IP values to NIC.",
      "title": "Ip Aliases"
    },
    "direct_connect": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Allow users to connect without using a proxy-machine.",
      "title": "Direct Connect"
    }
  },
  "required": [
    "network"
  ],
  "title": "NicModel",
  "type": "object"
}
```
</details>

## `ServerDetailsModel`

**Qualified name:** `common.models.agoge.ServerDetailsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `description` | `typing.Optional` | — | — | Useful services and programs this image is providing related to the workout. |
| `os` | `typing.Optional` | — | — | Operating system of the server |
| `labels` | `typing.Optional` | — | — | List of services and functionality provided on this server. |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Useful services and programs this image is providing related to the workout.",
      "title": "Description"
    },
    "os": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Operating system of the server",
      "title": "Os"
    },
    "labels": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "List of services and functionality provided on this server.",
      "title": "Labels"
    }
  },
  "title": "ServerDetailsModel",
  "type": "object"
}
```
</details>

## `ServerModel`

Servers used as part of a Unit or Unit Workout lab.<br>Partially based on information stored in AgogeImageModel objects.

**Qualified name:** `common.models.agoge.ServerModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `add_disk` | `typing.Optional` | — | `0` | Additional disk space of the server |
| `build_type` | `typing.Optional` | — | — | Build type of the server |
| `can_ip_forward` | `typing.Optional` | — | `False` | Whether IP forwarding is enabled |
| `community_server` | `typing.Optional` | — | `False` | Whether this server should be a shared server in a community build unit. |
| `details` | `typing.Optional` | — | — |  |
| `firewall_rules` | `typing.Optional` | — | — | List of firewall rules associated with server. |
| `hidden` | `typing.Optional` | — | `False` | Whether to display this server to students or not. |
| `human_interaction` | `typing.Optional` | — | — |  |
| `hostname` | `typing.Optional` | — | — | Public DNS record associated with server. |
| `image` | `str` | ✔️ | — | Image of the server |
| `machine_type` | `typing.Optional` | — | `e1-standard1` | Machine type of the server |
| `metadata` | `typing.Optional` | — | — | Metadata of the server |
| `guacamole_startup_script` | `typing.Optional` | — | — | Optional startup script for Guacamole service |
| `startup_scripts` | `typing.Optional` | — | — | Optional startup scripts to pass into server |
| `min_cpu_platform` | `typing.Optional` | — | `` | Minimum CPU platform of the server |
| `name` | `str` | ✔️ | — | Name of server. |
| `nics` | `typing.Optional` | — | — |  |
| `parent_build_type` | `typing.Optional` | — | — | Build type of parent object (i.e. workout, unit, etc.). |
| `parent_id` | `typing.Optional` | — | — | ID of parent object to associate with server. |
| `shutoff_timestamp` | `typing.Optional` | — | — | Timestamp of when server will shut down. |
| `sshkey` | `typing.Optional` | — | — | SSH key of the server |
| `tags` | `typing.Optional` | — | — | Optional field used for attaching specific firewall rules to machine |
| `state` | `typing.Optional` | — | — | Current build state of server |
| `state_timestamp` | `typing.Optional` | — | — | Timestamp of the server state |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "FirewallRuleModel": {
      "properties": {
        "name": {
          "description": "Name of the firewall rule",
          "title": "Name",
          "type": "string"
        },
        "network": {
          "description": "Network of the firewall rule",
          "title": "Network",
          "type": "string"
        },
        "action": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Action of the firewall rule",
          "title": "Action"
        },
        "target_tags": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "title": "Target Tags"
        },
        "protocol": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Protocol of the firewall rule",
          "title": "Protocol"
        },
        "ports": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of ports to apply rule to.",
          "title": "Ports"
        },
        "ip_ranges": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": [
            "0.0.0.0/0"
          ],
          "description": "Range of source or destination IPs to attach rule to.",
          "title": "Ip Ranges"
        },
        "direction": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "INGRESS",
          "description": "Direction of flow of traffic.",
          "title": "Direction"
        },
        "priority": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 1000,
          "description": "Rule priority.",
          "title": "Priority"
        }
      },
      "required": [
        "name",
        "network"
      ],
      "title": "FirewallRuleModel",
      "type": "object"
    },
    "HumanInteractionModel": {
      "properties": {
        "display": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Display"
        },
        "protocol": {
          "description": "Protocol of the human interaction",
          "title": "Protocol",
          "type": "string"
        },
        "username": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Username"
        },
        "password": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Password"
        },
        "ssh_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ssh Key"
        },
        "domain": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Domain"
        },
        "security_mode": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "nla",
          "description": "Security mode of the human interaction",
          "title": "Security Mode"
        }
      },
      "required": [
        "protocol"
      ],
      "title": "HumanInteractionModel",
      "type": "object"
    },
    "NicModel": {
      "properties": {
        "network": {
          "description": "Network of the NIC",
          "title": "Network",
          "type": "string"
        },
        "internal_ip": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Internal IP of the NIC",
          "title": "Internal Ip"
        },
        "subnet_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "default",
          "description": "Subnet name of the NIC",
          "title": "Subnet Name"
        },
        "external_nat": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Must be true if servers on network are intended to communicate outside of network.",
          "title": "External Nat"
        },
        "ip_aliases": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Assign multiple IP values to NIC.",
          "title": "Ip Aliases"
        },
        "direct_connect": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Allow users to connect without using a proxy-machine.",
          "title": "Direct Connect"
        }
      },
      "required": [
        "network"
      ],
      "title": "NicModel",
      "type": "object"
    },
    "ServerDetailsModel": {
      "properties": {
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Useful services and programs this image is providing related to the workout.",
          "title": "Description"
        },
        "os": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Operating system of the server",
          "title": "Os"
        },
        "labels": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of services and functionality provided on this server.",
          "title": "Labels"
        }
      },
      "title": "ServerDetailsModel",
      "type": "object"
    }
  },
  "description": "Servers used as part of a Unit or Unit Workout lab.\nPartially based on information stored in AgogeImageModel objects.",
  "properties": {
    "add_disk": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": 0,
      "description": "Additional disk space of the server",
      "title": "Add Disk"
    },
    "build_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Build type of the server",
      "title": "Build Type"
    },
    "can_ip_forward": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether IP forwarding is enabled",
      "title": "Can Ip Forward"
    },
    "community_server": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether this server should be a shared server in a community build unit.",
      "title": "Community Server"
    },
    "details": {
      "anyOf": [
        {
          "$ref": "#/$defs/ServerDetailsModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "firewall_rules": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/FirewallRuleModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "List of firewall rules associated with server.",
      "title": "Firewall Rules"
    },
    "hidden": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether to display this server to students or not.",
      "title": "Hidden"
    },
    "human_interaction": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/HumanInteractionModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Human Interaction"
    },
    "hostname": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Public DNS record associated with server.",
      "title": "Hostname"
    },
    "image": {
      "description": "Image of the server",
      "title": "Image",
      "type": "string"
    },
    "machine_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "e1-standard1",
      "description": "Machine type of the server",
      "title": "Machine Type"
    },
    "metadata": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Metadata of the server",
      "title": "Metadata"
    },
    "guacamole_startup_script": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional startup script for Guacamole service",
      "title": "Guacamole Startup Script"
    },
    "startup_scripts": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional startup scripts to pass into server",
      "title": "Startup Scripts"
    },
    "min_cpu_platform": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "",
      "description": "Minimum CPU platform of the server",
      "title": "Min Cpu Platform"
    },
    "name": {
      "description": "Name of server.",
      "title": "Name",
      "type": "string"
    },
    "nics": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/NicModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Nics"
    },
    "parent_build_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Build type of parent object (i.e. workout, unit, etc.).",
      "title": "Parent Build Type"
    },
    "parent_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "ID of parent object to associate with server.",
      "title": "Parent Id"
    },
    "shutoff_timestamp": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Timestamp of when server will shut down.",
      "title": "Shutoff Timestamp"
    },
    "sshkey": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "SSH key of the server",
      "title": "Sshkey"
    },
    "tags": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional field used for attaching specific firewall rules to machine",
      "title": "Tags"
    },
    "state": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Current build state of server",
      "title": "State"
    },
    "state_timestamp": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Timestamp of the server state",
      "title": "State Timestamp"
    }
  },
  "required": [
    "image",
    "name"
  ],
  "title": "ServerModel",
  "type": "object"
}
```
</details>

## `StandardMappingsModel`

**Qualified name:** `common.models.agoge.StandardMappingsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `framework` | `str` | ✔️ | — | Framework of the standard mapping |
| `mapping` | `str` | ✔️ | — | Mapping of the standard |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "framework": {
      "description": "Framework of the standard mapping",
      "title": "Framework",
      "type": "string"
    },
    "mapping": {
      "description": "Mapping of the standard",
      "title": "Mapping",
      "type": "string"
    }
  },
  "required": [
    "framework",
    "mapping"
  ],
  "title": "StandardMappingsModel",
  "type": "object"
}
```
</details>

## `SubNetworkModel`

**Qualified name:** `common.models.agoge.SubNetworkModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the subnetwork |
| `ip_subnet` | `str` | ✔️ | — | IP subnet of the subnetwork |
| `promiscuous_mode` | `typing.Optional` | — | `False` | Toggle promiscuous mode for this subnetwork |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "description": "Name of the subnetwork",
      "title": "Name",
      "type": "string"
    },
    "ip_subnet": {
      "description": "IP subnet of the subnetwork",
      "title": "Ip Subnet",
      "type": "string"
    },
    "promiscuous_mode": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Toggle promiscuous mode for this subnetwork",
      "title": "Promiscuous Mode"
    }
  },
  "required": [
    "name",
    "ip_subnet"
  ],
  "title": "SubNetworkModel",
  "type": "object"
}
```
</details>

## `TeachingConceptsModel`

**Qualified name:** `common.models.agoge.TeachingConceptsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `id` | `str` | ✔️ | — | ID of the teaching concept |
| `name` | `str` | ✔️ | — | Name of the teaching concept |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "description": "ID of the teaching concept",
      "title": "Id",
      "type": "string"
    },
    "name": {
      "description": "Name of the teaching concept",
      "title": "Name",
      "type": "string"
    }
  },
  "required": [
    "id",
    "name"
  ],
  "title": "TeachingConceptsModel",
  "type": "object"
}
```
</details>



## `UnitModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `id` | `str` | ✔️ | — | ID of the unit |
| `creation_timestamp` | `typing.Optional` | — | — |  |
| `version` | `str` | ✔️ | — | Version of the unit |
| `class_id` | `typing.Optional` | — | — |  |
| `instructor_id` | `typing.Union` | ✔️ | — | List of instructor IDs |
| `workspace_settings` | `typing.Optional` | — | — |  |
| `build_type` | `str` | ✔️ | — | Build type of the unit |
| `unit_type` | `typing.Optional` | — | `UnitType.SOLO` | Defines the type of unit setup. |
| `summary` | `AgogeSummaryModel` | ✔️ | — | Summary of the Agoge unit |
| `networks` | `typing.Optional` | — | — |  |
| `servers` | `typing.Optional` | — | — |  |
| `web_applications` | `typing.Optional` | — | — | Used for cloud container labs |
| `firewalls` | `typing.Optional` | — | — |  |
| `firewall_rules` | `typing.Optional` | — | — | These are ONLY set by the program to allow all internal traffic |
| `assessment` | `typing.Optional` | — | — | Use Agoge to provide grading support |
| `lms_integration` | `typing.Optional` | — | — | Use connected LMS to provide grading support and distribution functionality |
| `escape_room` | `typing.Optional` | — | — | Escape room units include additional specification of the escape room puzzles associated with each workout |
| `test` | `typing.Optional` | — | — | Whether the unit is a test. This helps in cleaning the datastore. |
| `join_code` | `typing.Optional` | — | — | Used to invite students to claim a unit workspace |
| `workout_duration_days` | `typing.Optional` | — | — | For asynchronous workout builds, specify to add an expiration timestamp for the workout. |
| `accessibility_features` | `typing.Optional` | — | `False` | Whether accessibility features are enabled or not |
| `state` | `typing.Optional` | — | — | Current build state of unit |
| `state_timestamp` | `typing.Optional` | — | — | Timestamp of the unit state |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "AgogeSummaryModel": {
      "properties": {
        "name": {
          "description": "Name of the Agoge summary",
          "title": "Name",
          "type": "string"
        },
        "description": {
          "description": "Description of the Agoge summary",
          "title": "Description",
          "type": "string"
        },
        "teacher_instructions_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "URL for teacher instructions",
          "title": "Teacher Instructions Url"
        },
        "student_instructions_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "URL for student instructions",
          "title": "Student Instructions Url"
        },
        "hourly_cost": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Hourly cost of the Agoge summary",
          "title": "Hourly Cost"
        },
        "author": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Author of the Agoge summary",
          "title": "Author"
        },
        "standard_mappings": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/StandardMappingsModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Curriculum standard mappings for this lab",
          "title": "Standard Mappings"
        },
        "tags": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/TeachingConceptsModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "description": "Key concepts that this build is intended to teach",
          "title": "Tags"
        }
      },
      "required": [
        "name",
        "description"
      ],
      "title": "AgogeSummaryModel",
      "type": "object"
    },
    "AssessmentModel": {
      "properties": {
        "questions": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/AssessmentQuestionModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Questions"
        },
        "assessment_script": {
          "anyOf": [
            {
              "$ref": "#/$defs/AssessmentScriptModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The assessment script for all indicated questions."
        },
        "key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Key used for decrypting workout secrets in container applications",
          "title": "Key"
        }
      },
      "title": "AssessmentModel",
      "type": "object"
    },
    "AssessmentQuestionModel": {
      "properties": {
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "An ID to use when referring to specific questions",
          "title": "Id"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The name of the question, which is also used for the workout-level assessment script.",
          "title": "Name"
        },
        "type": {
          "description": "Type of the question",
          "title": "Type",
          "type": "string"
        },
        "question": {
          "description": "Question text",
          "title": "Question",
          "type": "string"
        },
        "key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The value used for decrypting individual cryptographic questions",
          "title": "Key"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The answer to the question for questions of type input",
          "title": "Answer"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Complete"
        }
      },
      "required": [
        "type",
        "question"
      ],
      "title": "AssessmentQuestionModel",
      "type": "object"
    },
    "AssessmentScriptModel": {
      "properties": {
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        }
      },
      "title": "AssessmentScriptModel",
      "type": "object"
    },
    "EscapeRoomModel": {
      "properties": {
        "question": {
          "description": "The door to open in the escape room",
          "title": "Question",
          "type": "string"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Answer from the top level-question",
          "title": "Answer"
        },
        "responses": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "description": "Records the team's attempts to answer the question and escape",
          "title": "Responses"
        },
        "escaped": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether or not the team has successfully escaped",
          "title": "Escaped"
        },
        "time_limit": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 3600,
          "description": "Number of seconds the team has to escape from the room",
          "title": "Time Limit"
        },
        "start_time": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": 0.0,
          "description": "When the escape room started.",
          "title": "Start Time"
        },
        "remaining_time": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Remaining Time"
        },
        "puzzles": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/PuzzleModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Puzzles"
        }
      },
      "required": [
        "question"
      ],
      "title": "EscapeRoomModel",
      "type": "object"
    },
    "FirewallModel": {
      "properties": {
        "name": {
          "description": "Name of the firewall",
          "title": "Name",
          "type": "string"
        },
        "type": {
          "description": "Type of the firewall",
          "title": "Type",
          "type": "string"
        },
        "gateway": {
          "description": "Gateway of the firewall",
          "title": "Gateway",
          "type": "string"
        },
        "networks": {
          "description": "Networks of the firewall",
          "items": {
            "type": "string"
          },
          "title": "Networks",
          "type": "array"
        },
        "allow_outbound": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": true,
          "description": "If False, connections can still come in, but general outbound traffic will be denied",
          "title": "Allow Outbound"
        }
      },
      "required": [
        "name",
        "type",
        "gateway",
        "networks"
      ],
      "title": "FirewallModel",
      "type": "object"
    },
    "FirewallRuleModel": {
      "properties": {
        "name": {
          "description": "Name of the firewall rule",
          "title": "Name",
          "type": "string"
        },
        "network": {
          "description": "Network of the firewall rule",
          "title": "Network",
          "type": "string"
        },
        "action": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Action of the firewall rule",
          "title": "Action"
        },
        "target_tags": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "title": "Target Tags"
        },
        "protocol": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Protocol of the firewall rule",
          "title": "Protocol"
        },
        "ports": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of ports to apply rule to.",
          "title": "Ports"
        },
        "ip_ranges": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": [
            "0.0.0.0/0"
          ],
          "description": "Range of source or destination IPs to attach rule to.",
          "title": "Ip Ranges"
        },
        "direction": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "INGRESS",
          "description": "Direction of flow of traffic.",
          "title": "Direction"
        },
        "priority": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 1000,
          "description": "Rule priority.",
          "title": "Priority"
        }
      },
      "required": [
        "name",
        "network"
      ],
      "title": "FirewallRuleModel",
      "type": "object"
    },
    "HumanInteractionModel": {
      "properties": {
        "display": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Display"
        },
        "protocol": {
          "description": "Protocol of the human interaction",
          "title": "Protocol",
          "type": "string"
        },
        "username": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Username"
        },
        "password": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Password"
        },
        "ssh_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ssh Key"
        },
        "domain": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Domain"
        },
        "security_mode": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "nla",
          "description": "Security mode of the human interaction",
          "title": "Security Mode"
        }
      },
      "required": [
        "protocol"
      ],
      "title": "HumanInteractionModel",
      "type": "object"
    },
    "LMSConnectionModel": {
      "properties": {
        "lms_type": {
          "description": "The type of LMS this should integrate with.",
          "title": "Lms Type",
          "type": "string"
        },
        "api_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The API key from the user profile needed for connecting to the LMS",
          "title": "Api Key"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The LMS API URL",
          "title": "Url"
        },
        "course_code": {
          "description": "The course code to use for creating the LMS assignments",
          "title": "Course Code",
          "type": "integer"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Name of LMS course",
          "title": "Name"
        }
      },
      "required": [
        "lms_type",
        "course_code"
      ],
      "title": "LMSConnectionModel",
      "type": "object"
    },
    "LMSIntegrationModel": {
      "properties": {
        "lms_connection": {
          "anyOf": [
            {
              "$ref": "#/$defs/LMSConnectionModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The information needed to connect a lab to a course"
        },
        "course_work": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "assignment",
          "description": "Practice quiz or assignment",
          "title": "Course Work"
        },
        "due_at": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Due date for assignment",
          "title": "Due At"
        },
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Description of assignment",
          "title": "Description"
        },
        "allowed_attempts": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": -1.0,
          "description": "Attempts available for assignment, -1 is unlimited",
          "title": "Allowed Attempts"
        },
        "assessment_script": {
          "anyOf": [
            {
              "$ref": "#/$defs/AssessmentScriptModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The assessment script for all indicated questions."
        },
        "questions": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/LMSQuizQuestionsModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Questions"
        }
      },
      "title": "LMSIntegrationModel",
      "type": "object"
    },
    "LMSQuizAnswerModel": {
      "properties": {
        "answer_text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Answer text",
          "title": "Answer Text"
        },
        "weight": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": 0.0,
          "description": "Weight of the answer",
          "title": "Weight"
        }
      },
      "title": "LMSQuizAnswerModel",
      "type": "object"
    },
    "LMSQuizQuestionsModel": {
      "properties": {
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question name",
          "title": "Name"
        },
        "question_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Alternative field for question name (Canvas specific).",
          "title": "Question Name"
        },
        "question_text": {
          "description": "Question text",
          "title": "Question Text",
          "type": "string"
        },
        "question_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question type",
          "title": "Question Type"
        },
        "points_possible": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Points possible",
          "title": "Points Possible"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "bonus": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Whether to count this question as a bonus",
          "title": "Bonus"
        },
        "answers": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/LMSQuizAnswerModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question answers",
          "title": "Answers"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Used to mark completion for multi-step auto assessment scripts",
          "title": "Complete"
        }
      },
      "required": [
        "question_text"
      ],
      "title": "LMSQuizQuestionsModel",
      "type": "object"
    },
    "NetworkModel": {
      "properties": {
        "name": {
          "description": "Name of the network",
          "title": "Name",
          "type": "string"
        },
        "subnets": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/SubNetworkModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Subnets"
        },
        "reservations": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reservations"
        }
      },
      "required": [
        "name"
      ],
      "title": "NetworkModel",
      "type": "object"
    },
    "NicModel": {
      "properties": {
        "network": {
          "description": "Network of the NIC",
          "title": "Network",
          "type": "string"
        },
        "internal_ip": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Internal IP of the NIC",
          "title": "Internal Ip"
        },
        "subnet_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "default",
          "description": "Subnet name of the NIC",
          "title": "Subnet Name"
        },
        "external_nat": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Must be true if servers on network are intended to communicate outside of network.",
          "title": "External Nat"
        },
        "ip_aliases": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Assign multiple IP values to NIC.",
          "title": "Ip Aliases"
        },
        "direct_connect": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Allow users to connect without using a proxy-machine.",
          "title": "Direct Connect"
        }
      },
      "required": [
        "network"
      ],
      "title": "NicModel",
      "type": "object"
    },
    "PuzzleModel": {
      "properties": {
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "An ID to use when referring to specific puzzles",
          "title": "Id"
        },
        "instructions_url": {
          "anyOf": [
            {
              "format": "uri",
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "URL for puzzle instructions",
          "title": "Instructions Url"
        },
        "entry_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The type of entry to present to the user for solving the question",
          "title": "Entry Type"
        },
        "entry_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A name based on the entry_type to help build a URL for the student to click on.",
          "title": "Entry Name"
        },
        "type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "input",
          "description": "Type of the puzzle question",
          "title": "Type"
        },
        "summary": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Brief outline of what the puzzle is about",
          "title": "Summary"
        },
        "question": {
          "description": "Question text",
          "title": "Question",
          "type": "string"
        },
        "name": {
          "description": "Name of the puzzle",
          "title": "Name",
          "type": "string"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The answer to the question for questions of type input",
          "title": "Answer"
        },
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        },
        "responses": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "description": "Records the team's attempts to answer the question and escape",
          "title": "Responses"
        },
        "correct": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether the puzzle response is correct",
          "title": "Correct"
        },
        "reveal": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Information to reveal if they have the right answer",
          "title": "Reveal"
        }
      },
      "required": [
        "question",
        "name"
      ],
      "title": "PuzzleModel",
      "type": "object"
    },
    "ServerDetailsModel": {
      "properties": {
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Useful services and programs this image is providing related to the workout.",
          "title": "Description"
        },
        "os": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Operating system of the server",
          "title": "Os"
        },
        "labels": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of services and functionality provided on this server.",
          "title": "Labels"
        }
      },
      "title": "ServerDetailsModel",
      "type": "object"
    },
    "ServerModel": {
      "description": "Servers used as part of a Unit or Unit Workout lab.\nPartially based on information stored in AgogeImageModel objects.",
      "properties": {
        "add_disk": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 0,
          "description": "Additional disk space of the server",
          "title": "Add Disk"
        },
        "build_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Build type of the server",
          "title": "Build Type"
        },
        "can_ip_forward": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether IP forwarding is enabled",
          "title": "Can Ip Forward"
        },
        "community_server": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether this server should be a shared server in a community build unit.",
          "title": "Community Server"
        },
        "details": {
          "anyOf": [
            {
              "$ref": "#/$defs/ServerDetailsModel"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "firewall_rules": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/FirewallRuleModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of firewall rules associated with server.",
          "title": "Firewall Rules"
        },
        "hidden": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether to display this server to students or not.",
          "title": "Hidden"
        },
        "human_interaction": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/HumanInteractionModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Human Interaction"
        },
        "hostname": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Public DNS record associated with server.",
          "title": "Hostname"
        },
        "image": {
          "description": "Image of the server",
          "title": "Image",
          "type": "string"
        },
        "machine_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "e1-standard1",
          "description": "Machine type of the server",
          "title": "Machine Type"
        },
        "metadata": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Metadata of the server",
          "title": "Metadata"
        },
        "guacamole_startup_script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Optional startup script for Guacamole service",
          "title": "Guacamole Startup Script"
        },
        "startup_scripts": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Optional startup scripts to pass into server",
          "title": "Startup Scripts"
        },
        "min_cpu_platform": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "",
          "description": "Minimum CPU platform of the server",
          "title": "Min Cpu Platform"
        },
        "name": {
          "description": "Name of server.",
          "title": "Name",
          "type": "string"
        },
        "nics": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/NicModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Nics"
        },
        "parent_build_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Build type of parent object (i.e. workout, unit, etc.).",
          "title": "Parent Build Type"
        },
        "parent_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "ID of parent object to associate with server.",
          "title": "Parent Id"
        },
        "shutoff_timestamp": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Timestamp of when server will shut down.",
          "title": "Shutoff Timestamp"
        },
        "sshkey": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "SSH key of the server",
          "title": "Sshkey"
        },
        "tags": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Optional field used for attaching specific firewall rules to machine",
          "title": "Tags"
        },
        "state": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Current build state of server",
          "title": "State"
        },
        "state_timestamp": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Timestamp of the server state",
          "title": "State Timestamp"
        }
      },
      "required": [
        "image",
        "name"
      ],
      "title": "ServerModel",
      "type": "object"
    },
    "StandardMappingsModel": {
      "properties": {
        "framework": {
          "description": "Framework of the standard mapping",
          "title": "Framework",
          "type": "string"
        },
        "mapping": {
          "description": "Mapping of the standard",
          "title": "Mapping",
          "type": "string"
        }
      },
      "required": [
        "framework",
        "mapping"
      ],
      "title": "StandardMappingsModel",
      "type": "object"
    },
    "SubNetworkModel": {
      "properties": {
        "name": {
          "description": "Name of the subnetwork",
          "title": "Name",
          "type": "string"
        },
        "ip_subnet": {
          "description": "IP subnet of the subnetwork",
          "title": "Ip Subnet",
          "type": "string"
        },
        "promiscuous_mode": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Toggle promiscuous mode for this subnetwork",
          "title": "Promiscuous Mode"
        }
      },
      "required": [
        "name",
        "ip_subnet"
      ],
      "title": "SubNetworkModel",
      "type": "object"
    },
    "TeachingConceptsModel": {
      "properties": {
        "id": {
          "description": "ID of the teaching concept",
          "title": "Id",
          "type": "string"
        },
        "name": {
          "description": "Name of the teaching concept",
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name"
      ],
      "title": "TeachingConceptsModel",
      "type": "object"
    },
    "WebApplicationModel": {
      "properties": {
        "name": {
          "description": "Display name of the container",
          "title": "Name",
          "type": "string"
        },
        "host_name": {
          "description": "Host name for the URL",
          "title": "Host Name",
          "type": "string"
        },
        "starting_directory": {
          "description": "The starting web directory for the container URL.",
          "title": "Starting Directory",
          "type": "string"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Full path of web application",
          "title": "Url"
        }
      },
      "required": [
        "name",
        "host_name",
        "starting_directory"
      ],
      "title": "WebApplicationModel",
      "type": "object"
    },
    "WorkspaceSettingsModel": {
      "properties": {
        "count": {
          "description": "The number of distinct workstation builds to deploy",
          "title": "Count",
          "type": "integer"
        },
        "registration_required": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether students must login to access this build",
          "title": "Registration Required"
        },
        "student_emails": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Email addresses of students when registration is required",
          "title": "Student Emails"
        },
        "student_names": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Name of the student assigned to the workspaces",
          "title": "Student Names"
        },
        "expires": {
          "description": "UTC timestamp of date when resources are available until.",
          "title": "Expires",
          "type": "number"
        }
      },
      "required": [
        "count",
        "expires"
      ],
      "title": "WorkspaceSettingsModel",
      "type": "object"
    }
  },
  "properties": {
    "id": {
      "description": "ID of the unit",
      "title": "Id",
      "type": "string"
    },
    "creation_timestamp": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Creation Timestamp"
    },
    "version": {
      "description": "Version of the unit",
      "title": "Version",
      "type": "string"
    },
    "class_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Class Id"
    },
    "instructor_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      ],
      "description": "List of instructor IDs",
      "title": "Instructor Id"
    },
    "workspace_settings": {
      "anyOf": [
        {
          "$ref": "#/$defs/WorkspaceSettingsModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "build_type": {
      "description": "Build type of the unit",
      "title": "Build Type",
      "type": "string"
    },
    "unit_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "solo",
      "description": "Defines the type of unit setup.",
      "title": "Unit Type"
    },
    "summary": {
      "allOf": [
        {
          "$ref": "#/$defs/AgogeSummaryModel"
        }
      ],
      "description": "Summary of the Agoge unit"
    },
    "networks": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/NetworkModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Networks"
    },
    "servers": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/ServerModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Servers"
    },
    "web_applications": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/WebApplicationModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Used for cloud container labs",
      "title": "Web Applications"
    },
    "firewalls": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/FirewallModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Firewalls"
    },
    "firewall_rules": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/FirewallRuleModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "These are ONLY set by the program to allow all internal traffic",
      "title": "Firewall Rules"
    },
    "assessment": {
      "anyOf": [
        {
          "$ref": "#/$defs/AssessmentModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Use Agoge to provide grading support"
    },
    "lms_integration": {
      "anyOf": [
        {
          "$ref": "#/$defs/LMSIntegrationModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Use connected LMS to provide grading support and distribution functionality"
    },
    "escape_room": {
      "anyOf": [
        {
          "$ref": "#/$defs/EscapeRoomModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Escape room units include additional specification of the escape room puzzles associated with each workout"
    },
    "test": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Whether the unit is a test. This helps in cleaning the datastore.",
      "title": "Test"
    },
    "join_code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Used to invite students to claim a unit workspace",
      "title": "Join Code"
    },
    "workout_duration_days": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "For asynchronous workout builds, specify to add an expiration timestamp for the workout.",
      "title": "Workout Duration Days"
    },
    "accessibility_features": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether accessibility features are enabled or not",
      "title": "Accessibility Features"
    },
    "state": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Current build state of unit",
      "title": "State"
    },
    "state_timestamp": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Timestamp of the unit state",
      "title": "State Timestamp"
    }
  },
  "required": [
    "id",
    "version",
    "instructor_id",
    "build_type",
    "summary"
  ],
  "title": "UnitModel",
  "type": "object"
}
```
</details>

## `AgogeSummaryModel`

**Qualified name:** `common.models.agoge.AgogeSummaryModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the Agoge summary |
| `description` | `str` | ✔️ | — | Description of the Agoge summary |
| `teacher_instructions_url` | `typing.Optional` | — | — | URL for teacher instructions |
| `student_instructions_url` | `typing.Optional` | — | — | URL for student instructions |
| `hourly_cost` | `typing.Optional` | — | — | Hourly cost of the Agoge summary |
| `author` | `typing.Optional` | — | — | Author of the Agoge summary |
| `standard_mappings` | `typing.Optional` | — | — | Curriculum standard mappings for this lab |
| `tags` | `typing.Optional` | — | `PydanticUndefined` | Key concepts that this build is intended to teach |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "StandardMappingsModel": {
      "properties": {
        "framework": {
          "description": "Framework of the standard mapping",
          "title": "Framework",
          "type": "string"
        },
        "mapping": {
          "description": "Mapping of the standard",
          "title": "Mapping",
          "type": "string"
        }
      },
      "required": [
        "framework",
        "mapping"
      ],
      "title": "StandardMappingsModel",
      "type": "object"
    },
    "TeachingConceptsModel": {
      "properties": {
        "id": {
          "description": "ID of the teaching concept",
          "title": "Id",
          "type": "string"
        },
        "name": {
          "description": "Name of the teaching concept",
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name"
      ],
      "title": "TeachingConceptsModel",
      "type": "object"
    }
  },
  "properties": {
    "name": {
      "description": "Name of the Agoge summary",
      "title": "Name",
      "type": "string"
    },
    "description": {
      "description": "Description of the Agoge summary",
      "title": "Description",
      "type": "string"
    },
    "teacher_instructions_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "URL for teacher instructions",
      "title": "Teacher Instructions Url"
    },
    "student_instructions_url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "URL for student instructions",
      "title": "Student Instructions Url"
    },
    "hourly_cost": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Hourly cost of the Agoge summary",
      "title": "Hourly Cost"
    },
    "author": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Author of the Agoge summary",
      "title": "Author"
    },
    "standard_mappings": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/StandardMappingsModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Curriculum standard mappings for this lab",
      "title": "Standard Mappings"
    },
    "tags": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/TeachingConceptsModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "description": "Key concepts that this build is intended to teach",
      "title": "Tags"
    }
  },
  "required": [
    "name",
    "description"
  ],
  "title": "AgogeSummaryModel",
  "type": "object"
}
```
</details>

## `AssessmentModel`

**Qualified name:** `common.models.agoge.AssessmentModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `questions` | `typing.Optional` | — | — |  |
| `assessment_script` | `typing.Optional` | — | — | The assessment script for all indicated questions. |
| `key` | `typing.Optional` | — | — | Key used for decrypting workout secrets in container applications |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "AssessmentQuestionModel": {
      "properties": {
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "An ID to use when referring to specific questions",
          "title": "Id"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The name of the question, which is also used for the workout-level assessment script.",
          "title": "Name"
        },
        "type": {
          "description": "Type of the question",
          "title": "Type",
          "type": "string"
        },
        "question": {
          "description": "Question text",
          "title": "Question",
          "type": "string"
        },
        "key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The value used for decrypting individual cryptographic questions",
          "title": "Key"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The answer to the question for questions of type input",
          "title": "Answer"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Complete"
        }
      },
      "required": [
        "type",
        "question"
      ],
      "title": "AssessmentQuestionModel",
      "type": "object"
    },
    "AssessmentScriptModel": {
      "properties": {
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        }
      },
      "title": "AssessmentScriptModel",
      "type": "object"
    }
  },
  "properties": {
    "questions": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/AssessmentQuestionModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Questions"
    },
    "assessment_script": {
      "anyOf": [
        {
          "$ref": "#/$defs/AssessmentScriptModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The assessment script for all indicated questions."
    },
    "key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Key used for decrypting workout secrets in container applications",
      "title": "Key"
    }
  },
  "title": "AssessmentModel",
  "type": "object"
}
```
</details>

## `AssessmentQuestionModel`

**Qualified name:** `common.models.agoge.AssessmentQuestionModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `id` | `typing.Optional` | — | `PydanticUndefined` | An ID to use when referring to specific questions |
| `name` | `typing.Optional` | — | — | The name of the question, which is also used for the workout-level assessment script. |
| `type` | `str` | ✔️ | — | Type of the question |
| `question` | `str` | ✔️ | — | Question text |
| `key` | `typing.Optional` | — | — | The value used for decrypting individual cryptographic questions |
| `answer` | `typing.Optional` | — | — | The answer to the question for questions of type input |
| `script_assessment` | `typing.Optional` | — | `False` |  |
| `complete` | `typing.Optional` | — | `False` |  |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "An ID to use when referring to specific questions",
      "title": "Id"
    },
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The name of the question, which is also used for the workout-level assessment script.",
      "title": "Name"
    },
    "type": {
      "description": "Type of the question",
      "title": "Type",
      "type": "string"
    },
    "question": {
      "description": "Question text",
      "title": "Question",
      "type": "string"
    },
    "key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The value used for decrypting individual cryptographic questions",
      "title": "Key"
    },
    "answer": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The answer to the question for questions of type input",
      "title": "Answer"
    },
    "script_assessment": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Script Assessment"
    },
    "complete": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Complete"
    }
  },
  "required": [
    "type",
    "question"
  ],
  "title": "AssessmentQuestionModel",
  "type": "object"
}
```
</details>

## `AssessmentScriptModel`

**Qualified name:** `common.models.agoge.AssessmentScriptModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `script` | `typing.Optional` | — | — | script name (e.g. attack.py) |
| `script_language` | `typing.Optional` | — | — | e.g. python |
| `server` | `typing.Optional` | — | — | Server that runs script. |
| `operating_system` | `typing.Optional` | — | — | Target server operating system |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "script": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "script name (e.g. attack.py)",
      "title": "Script"
    },
    "script_language": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "e.g. python",
      "title": "Script Language"
    },
    "server": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Server that runs script.",
      "title": "Server"
    },
    "operating_system": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Target server operating system",
      "title": "Operating System"
    }
  },
  "title": "AssessmentScriptModel",
  "type": "object"
}
```
</details>

## `EscapeRoomModel`

**Qualified name:** `common.models.agoge.EscapeRoomModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `question` | `str` | ✔️ | — | The door to open in the escape room |
| `answer` | `typing.Optional` | — | — | Answer from the top level-question |
| `responses` | `typing.Optional` | — | `PydanticUndefined` | Records the team's attempts to answer the question and escape |
| `escaped` | `typing.Optional` | — | `False` | Whether or not the team has successfully escaped |
| `time_limit` | `typing.Optional` | — | `3600` | Number of seconds the team has to escape from the room |
| `start_time` | `typing.Optional` | — | `0.0` | When the escape room started. |
| `remaining_time` | `typing.Optional` | — | — |  |
| `puzzles` | `typing.Optional` | — | — |  |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "PuzzleModel": {
      "properties": {
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "An ID to use when referring to specific puzzles",
          "title": "Id"
        },
        "instructions_url": {
          "anyOf": [
            {
              "format": "uri",
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "URL for puzzle instructions",
          "title": "Instructions Url"
        },
        "entry_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The type of entry to present to the user for solving the question",
          "title": "Entry Type"
        },
        "entry_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A name based on the entry_type to help build a URL for the student to click on.",
          "title": "Entry Name"
        },
        "type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "input",
          "description": "Type of the puzzle question",
          "title": "Type"
        },
        "summary": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Brief outline of what the puzzle is about",
          "title": "Summary"
        },
        "question": {
          "description": "Question text",
          "title": "Question",
          "type": "string"
        },
        "name": {
          "description": "Name of the puzzle",
          "title": "Name",
          "type": "string"
        },
        "answer": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The answer to the question for questions of type input",
          "title": "Answer"
        },
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        },
        "responses": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "description": "Records the team's attempts to answer the question and escape",
          "title": "Responses"
        },
        "correct": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Whether the puzzle response is correct",
          "title": "Correct"
        },
        "reveal": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Information to reveal if they have the right answer",
          "title": "Reveal"
        }
      },
      "required": [
        "question",
        "name"
      ],
      "title": "PuzzleModel",
      "type": "object"
    }
  },
  "properties": {
    "question": {
      "description": "The door to open in the escape room",
      "title": "Question",
      "type": "string"
    },
    "answer": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Answer from the top level-question",
      "title": "Answer"
    },
    "responses": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "description": "Records the team's attempts to answer the question and escape",
      "title": "Responses"
    },
    "escaped": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether or not the team has successfully escaped",
      "title": "Escaped"
    },
    "time_limit": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": 3600,
      "description": "Number of seconds the team has to escape from the room",
      "title": "Time Limit"
    },
    "start_time": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": 0.0,
      "description": "When the escape room started.",
      "title": "Start Time"
    },
    "remaining_time": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Remaining Time"
    },
    "puzzles": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/PuzzleModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Puzzles"
    }
  },
  "required": [
    "question"
  ],
  "title": "EscapeRoomModel",
  "type": "object"
}
```
</details>

## `FirewallModel`

**Qualified name:** `common.models.agoge.FirewallModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the firewall |
| `type` | `str` | ✔️ | — | Type of the firewall |
| `gateway` | `str` | ✔️ | — | Gateway of the firewall |
| `networks` | `List[str]` | ✔️ | — | Networks of the firewall |
| `allow_outbound` | `typing.Optional` | — | `True` | If False, connections can still come in, but general outbound traffic will be denied |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "description": "Name of the firewall",
      "title": "Name",
      "type": "string"
    },
    "type": {
      "description": "Type of the firewall",
      "title": "Type",
      "type": "string"
    },
    "gateway": {
      "description": "Gateway of the firewall",
      "title": "Gateway",
      "type": "string"
    },
    "networks": {
      "description": "Networks of the firewall",
      "items": {
        "type": "string"
      },
      "title": "Networks",
      "type": "array"
    },
    "allow_outbound": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": true,
      "description": "If False, connections can still come in, but general outbound traffic will be denied",
      "title": "Allow Outbound"
    }
  },
  "required": [
    "name",
    "type",
    "gateway",
    "networks"
  ],
  "title": "FirewallModel",
  "type": "object"
}
```
</details>

## `FirewallRuleModel`

**Qualified name:** `common.models.agoge.FirewallRuleModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the firewall rule |
| `network` | `str` | ✔️ | — | Network of the firewall rule |
| `action` | `typing.Optional` | — | — | Action of the firewall rule |
| `target_tags` | `typing.Optional` | — | `PydanticUndefined` |  |
| `protocol` | `typing.Optional` | — | — | Protocol of the firewall rule |
| `ports` | `typing.Optional` | — | — | List of ports to apply rule to. |
| `ip_ranges` | `typing.Optional` | — | `['0.0.0.0/0']` | Range of source or destination IPs to attach rule to. |
| `direction` | `typing.Optional` | — | `INGRESS` | Direction of flow of traffic. |
| `priority` | `typing.Optional` | — | `1000` | Rule priority. |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "description": "Name of the firewall rule",
      "title": "Name",
      "type": "string"
    },
    "network": {
      "description": "Network of the firewall rule",
      "title": "Network",
      "type": "string"
    },
    "action": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Action of the firewall rule",
      "title": "Action"
    },
    "target_tags": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Target Tags"
    },
    "protocol": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Protocol of the firewall rule",
      "title": "Protocol"
    },
    "ports": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "List of ports to apply rule to.",
      "title": "Ports"
    },
    "ip_ranges": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": [
        "0.0.0.0/0"
      ],
      "description": "Range of source or destination IPs to attach rule to.",
      "title": "Ip Ranges"
    },
    "direction": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "INGRESS",
      "description": "Direction of flow of traffic.",
      "title": "Direction"
    },
    "priority": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": 1000,
      "description": "Rule priority.",
      "title": "Priority"
    }
  },
  "required": [
    "name",
    "network"
  ],
  "title": "FirewallRuleModel",
  "type": "object"
}
```
</details>

## `HumanInteractionModel`

**Qualified name:** `common.models.agoge.HumanInteractionModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `display` | `typing.Optional` | — | `False` |  |
| `protocol` | `str` | ✔️ | — | Protocol of the human interaction |
| `username` | `typing.Optional` | — | — |  |
| `password` | `typing.Optional` | — | — |  |
| `ssh_key` | `typing.Optional` | — | — |  |
| `domain` | `typing.Optional` | — | — |  |
| `security_mode` | `typing.Optional` | — | `SecurityModes.NLA` | Security mode of the human interaction |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "display": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Display"
    },
    "protocol": {
      "description": "Protocol of the human interaction",
      "title": "Protocol",
      "type": "string"
    },
    "username": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Username"
    },
    "password": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Password"
    },
    "ssh_key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Ssh Key"
    },
    "domain": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Domain"
    },
    "security_mode": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "nla",
      "description": "Security mode of the human interaction",
      "title": "Security Mode"
    }
  },
  "required": [
    "protocol"
  ],
  "title": "HumanInteractionModel",
  "type": "object"
}
```
</details>

## `LMSConnectionModel`

**Qualified name:** `common.models.agoge.LMSConnectionModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `lms_type` | `str` | ✔️ | — | The type of LMS this should integrate with. |
| `api_key` | `typing.Optional` | — | — | The API key from the user profile needed for connecting to the LMS |
| `url` | `typing.Optional` | — | — | The LMS API URL |
| `course_code` | `int` | ✔️ | — | The course code to use for creating the LMS assignments |
| `name` | `typing.Optional` | — | — | Name of LMS course |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "lms_type": {
      "description": "The type of LMS this should integrate with.",
      "title": "Lms Type",
      "type": "string"
    },
    "api_key": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The API key from the user profile needed for connecting to the LMS",
      "title": "Api Key"
    },
    "url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The LMS API URL",
      "title": "Url"
    },
    "course_code": {
      "description": "The course code to use for creating the LMS assignments",
      "title": "Course Code",
      "type": "integer"
    },
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Name of LMS course",
      "title": "Name"
    }
  },
  "required": [
    "lms_type",
    "course_code"
  ],
  "title": "LMSConnectionModel",
  "type": "object"
}
```
</details>

## `LMSIntegrationModel`

**Qualified name:** `common.models.agoge.LMSIntegrationModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `lms_connection` | `typing.Optional` | — | — | The information needed to connect a lab to a course |
| `course_work` | `typing.Optional` | — | `assignment` | Practice quiz or assignment |
| `due_at` | `typing.Optional` | — | — | Due date for assignment |
| `description` | `typing.Optional` | — | — | Description of assignment |
| `allowed_attempts` | `typing.Optional` | — | `-1.0` | Attempts available for assignment, -1 is unlimited |
| `assessment_script` | `typing.Optional` | — | — | The assessment script for all indicated questions. |
| `questions` | `typing.Optional` | — | — |  |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "AssessmentScriptModel": {
      "properties": {
        "script": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "script name (e.g. attack.py)",
          "title": "Script"
        },
        "script_language": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "e.g. python",
          "title": "Script Language"
        },
        "server": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Server that runs script.",
          "title": "Server"
        },
        "operating_system": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target server operating system",
          "title": "Operating System"
        }
      },
      "title": "AssessmentScriptModel",
      "type": "object"
    },
    "LMSConnectionModel": {
      "properties": {
        "lms_type": {
          "description": "The type of LMS this should integrate with.",
          "title": "Lms Type",
          "type": "string"
        },
        "api_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The API key from the user profile needed for connecting to the LMS",
          "title": "Api Key"
        },
        "url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The LMS API URL",
          "title": "Url"
        },
        "course_code": {
          "description": "The course code to use for creating the LMS assignments",
          "title": "Course Code",
          "type": "integer"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Name of LMS course",
          "title": "Name"
        }
      },
      "required": [
        "lms_type",
        "course_code"
      ],
      "title": "LMSConnectionModel",
      "type": "object"
    },
    "LMSQuizAnswerModel": {
      "properties": {
        "answer_text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Answer text",
          "title": "Answer Text"
        },
        "weight": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": 0.0,
          "description": "Weight of the answer",
          "title": "Weight"
        }
      },
      "title": "LMSQuizAnswerModel",
      "type": "object"
    },
    "LMSQuizQuestionsModel": {
      "properties": {
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question name",
          "title": "Name"
        },
        "question_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Alternative field for question name (Canvas specific).",
          "title": "Question Name"
        },
        "question_text": {
          "description": "Question text",
          "title": "Question Text",
          "type": "string"
        },
        "question_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question type",
          "title": "Question Type"
        },
        "points_possible": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Points possible",
          "title": "Points Possible"
        },
        "script_assessment": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Script Assessment"
        },
        "bonus": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Whether to count this question as a bonus",
          "title": "Bonus"
        },
        "answers": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/LMSQuizAnswerModel"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Question answers",
          "title": "Answers"
        },
        "complete": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Used to mark completion for multi-step auto assessment scripts",
          "title": "Complete"
        }
      },
      "required": [
        "question_text"
      ],
      "title": "LMSQuizQuestionsModel",
      "type": "object"
    }
  },
  "properties": {
    "lms_connection": {
      "anyOf": [
        {
          "$ref": "#/$defs/LMSConnectionModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The information needed to connect a lab to a course"
    },
    "course_work": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "assignment",
      "description": "Practice quiz or assignment",
      "title": "Course Work"
    },
    "due_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Due date for assignment",
      "title": "Due At"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Description of assignment",
      "title": "Description"
    },
    "allowed_attempts": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": -1.0,
      "description": "Attempts available for assignment, -1 is unlimited",
      "title": "Allowed Attempts"
    },
    "assessment_script": {
      "anyOf": [
        {
          "$ref": "#/$defs/AssessmentScriptModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The assessment script for all indicated questions."
    },
    "questions": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/LMSQuizQuestionsModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Questions"
    }
  },
  "title": "LMSIntegrationModel",
  "type": "object"
}
```
</details>

## `LMSQuizAnswerModel`

**Qualified name:** `common.models.agoge.LMSQuizAnswerModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `answer_text` | `typing.Optional` | — | — | Answer text |
| `weight` | `typing.Optional` | — | `0.0` | Weight of the answer |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "answer_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Answer text",
      "title": "Answer Text"
    },
    "weight": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": 0.0,
      "description": "Weight of the answer",
      "title": "Weight"
    }
  },
  "title": "LMSQuizAnswerModel",
  "type": "object"
}
```
</details>

## `LMSQuizQuestionsModel`

**Qualified name:** `common.models.agoge.LMSQuizQuestionsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `typing.Optional` | — | — | Question name |
| `question_name` | `typing.Optional` | — | — | Alternative field for question name (Canvas specific). |
| `question_text` | `str` | ✔️ | — | Question text |
| `question_type` | `typing.Optional` | — | — | Question type |
| `points_possible` | `typing.Optional` | — | — | Points possible |
| `script_assessment` | `typing.Optional` | — | `False` |  |
| `bonus` | `typing.Optional` | — | — | Whether to count this question as a bonus |
| `answers` | `typing.Optional` | — | — | Question answers |
| `complete` | `typing.Optional` | — | — | Used to mark completion for multi-step auto assessment scripts |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "LMSQuizAnswerModel": {
      "properties": {
        "answer_text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Answer text",
          "title": "Answer Text"
        },
        "weight": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": 0.0,
          "description": "Weight of the answer",
          "title": "Weight"
        }
      },
      "title": "LMSQuizAnswerModel",
      "type": "object"
    }
  },
  "properties": {
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Question name",
      "title": "Name"
    },
    "question_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Alternative field for question name (Canvas specific).",
      "title": "Question Name"
    },
    "question_text": {
      "description": "Question text",
      "title": "Question Text",
      "type": "string"
    },
    "question_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Question type",
      "title": "Question Type"
    },
    "points_possible": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Points possible",
      "title": "Points Possible"
    },
    "script_assessment": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "title": "Script Assessment"
    },
    "bonus": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Whether to count this question as a bonus",
      "title": "Bonus"
    },
    "answers": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/LMSQuizAnswerModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Question answers",
      "title": "Answers"
    },
    "complete": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Used to mark completion for multi-step auto assessment scripts",
      "title": "Complete"
    }
  },
  "required": [
    "question_text"
  ],
  "title": "LMSQuizQuestionsModel",
  "type": "object"
}
```
</details>

## `NetworkModel`

**Qualified name:** `common.models.agoge.NetworkModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the network |
| `subnets` | `typing.Optional` | — | — |  |
| `reservations` | `typing.Optional` | — | — |  |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "SubNetworkModel": {
      "properties": {
        "name": {
          "description": "Name of the subnetwork",
          "title": "Name",
          "type": "string"
        },
        "ip_subnet": {
          "description": "IP subnet of the subnetwork",
          "title": "Ip Subnet",
          "type": "string"
        },
        "promiscuous_mode": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Toggle promiscuous mode for this subnetwork",
          "title": "Promiscuous Mode"
        }
      },
      "required": [
        "name",
        "ip_subnet"
      ],
      "title": "SubNetworkModel",
      "type": "object"
    }
  },
  "properties": {
    "name": {
      "description": "Name of the network",
      "title": "Name",
      "type": "string"
    },
    "subnets": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/SubNetworkModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Subnets"
    },
    "reservations": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Reservations"
    }
  },
  "required": [
    "name"
  ],
  "title": "NetworkModel",
  "type": "object"
}
```
</details>

## `NicModel`

**Qualified name:** `common.models.agoge.NicModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `network` | `str` | ✔️ | — | Network of the NIC |
| `internal_ip` | `typing.Optional` | — | — | Internal IP of the NIC |
| `subnet_name` | `typing.Optional` | — | `default` | Subnet name of the NIC |
| `external_nat` | `typing.Optional` | — | `False` | Must be true if servers on network are intended to communicate outside of network. |
| `ip_aliases` | `typing.Optional` | — | — | Assign multiple IP values to NIC. |
| `direct_connect` | `typing.Optional` | — | `False` | Allow users to connect without using a proxy-machine. |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "network": {
      "description": "Network of the NIC",
      "title": "Network",
      "type": "string"
    },
    "internal_ip": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Internal IP of the NIC",
      "title": "Internal Ip"
    },
    "subnet_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "default",
      "description": "Subnet name of the NIC",
      "title": "Subnet Name"
    },
    "external_nat": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Must be true if servers on network are intended to communicate outside of network.",
      "title": "External Nat"
    },
    "ip_aliases": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Assign multiple IP values to NIC.",
      "title": "Ip Aliases"
    },
    "direct_connect": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Allow users to connect without using a proxy-machine.",
      "title": "Direct Connect"
    }
  },
  "required": [
    "network"
  ],
  "title": "NicModel",
  "type": "object"
}
```
</details>

## `PuzzleModel`

**Qualified name:** `common.models.agoge.PuzzleModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `id` | `typing.Optional` | — | `PydanticUndefined` | An ID to use when referring to specific puzzles |
| `instructions_url` | `typing.Union` | — | — | URL for puzzle instructions |
| `entry_type` | `typing.Optional` | — | — | The type of entry to present to the user for solving the question |
| `entry_name` | `typing.Optional` | — | — | A name based on the entry_type to help build a URL for the student to click on. |
| `type` | `typing.Optional` | — | `QuestionTypes.INPUT` | Type of the puzzle question |
| `summary` | `typing.Optional` | — | — | Brief outline of what the puzzle is about |
| `question` | `str` | ✔️ | — | Question text |
| `name` | `str` | ✔️ | — | Name of the puzzle |
| `answer` | `typing.Optional` | — | — | The answer to the question for questions of type input |
| `script` | `typing.Optional` | — | — | script name (e.g. attack.py) |
| `script_language` | `typing.Optional` | — | — | e.g. python |
| `server` | `typing.Optional` | — | — | Server that runs script. |
| `operating_system` | `typing.Optional` | — | — | Target server operating system |
| `responses` | `typing.Optional` | — | `PydanticUndefined` | Records the team's attempts to answer the question and escape |
| `correct` | `typing.Optional` | — | `False` | Whether the puzzle response is correct |
| `reveal` | `typing.Optional` | — | — | Information to reveal if they have the right answer |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "description": "An ID to use when referring to specific puzzles",
      "title": "Id"
    },
    "instructions_url": {
      "anyOf": [
        {
          "format": "uri",
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "URL for puzzle instructions",
      "title": "Instructions Url"
    },
    "entry_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The type of entry to present to the user for solving the question",
      "title": "Entry Type"
    },
    "entry_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A name based on the entry_type to help build a URL for the student to click on.",
      "title": "Entry Name"
    },
    "type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "input",
      "description": "Type of the puzzle question",
      "title": "Type"
    },
    "summary": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Brief outline of what the puzzle is about",
      "title": "Summary"
    },
    "question": {
      "description": "Question text",
      "title": "Question",
      "type": "string"
    },
    "name": {
      "description": "Name of the puzzle",
      "title": "Name",
      "type": "string"
    },
    "answer": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The answer to the question for questions of type input",
      "title": "Answer"
    },
    "script": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "script name (e.g. attack.py)",
      "title": "Script"
    },
    "script_language": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "e.g. python",
      "title": "Script Language"
    },
    "server": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Server that runs script.",
      "title": "Server"
    },
    "operating_system": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Target server operating system",
      "title": "Operating System"
    },
    "responses": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "description": "Records the team's attempts to answer the question and escape",
      "title": "Responses"
    },
    "correct": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether the puzzle response is correct",
      "title": "Correct"
    },
    "reveal": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Information to reveal if they have the right answer",
      "title": "Reveal"
    }
  },
  "required": [
    "question",
    "name"
  ],
  "title": "PuzzleModel",
  "type": "object"
}
```
</details>

## `ServerDetailsModel`

**Qualified name:** `common.models.agoge.ServerDetailsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `description` | `typing.Optional` | — | — | Useful services and programs this image is providing related to the workout. |
| `os` | `typing.Optional` | — | — | Operating system of the server |
| `labels` | `typing.Optional` | — | — | List of services and functionality provided on this server. |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Useful services and programs this image is providing related to the workout.",
      "title": "Description"
    },
    "os": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Operating system of the server",
      "title": "Os"
    },
    "labels": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "List of services and functionality provided on this server.",
      "title": "Labels"
    }
  },
  "title": "ServerDetailsModel",
  "type": "object"
}
```
</details>

## `ServerModel`

Servers used as part of a Unit or Unit Workout lab.<br>Partially based on information stored in AgogeImageModel objects.

**Qualified name:** `common.models.agoge.ServerModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `add_disk` | `typing.Optional` | — | `0` | Additional disk space of the server |
| `build_type` | `typing.Optional` | — | — | Build type of the server |
| `can_ip_forward` | `typing.Optional` | — | `False` | Whether IP forwarding is enabled |
| `community_server` | `typing.Optional` | — | `False` | Whether this server should be a shared server in a community build unit. |
| `details` | `typing.Optional` | — | — |  |
| `firewall_rules` | `typing.Optional` | — | — | List of firewall rules associated with server. |
| `hidden` | `typing.Optional` | — | `False` | Whether to display this server to students or not. |
| `human_interaction` | `typing.Optional` | — | — |  |
| `hostname` | `typing.Optional` | — | — | Public DNS record associated with server. |
| `image` | `str` | ✔️ | — | Image of the server |
| `machine_type` | `typing.Optional` | — | `e1-standard1` | Machine type of the server |
| `metadata` | `typing.Optional` | — | — | Metadata of the server |
| `guacamole_startup_script` | `typing.Optional` | — | — | Optional startup script for Guacamole service |
| `startup_scripts` | `typing.Optional` | — | — | Optional startup scripts to pass into server |
| `min_cpu_platform` | `typing.Optional` | — | `` | Minimum CPU platform of the server |
| `name` | `str` | ✔️ | — | Name of server. |
| `nics` | `typing.Optional` | — | — |  |
| `parent_build_type` | `typing.Optional` | — | — | Build type of parent object (i.e. workout, unit, etc.). |
| `parent_id` | `typing.Optional` | — | — | ID of parent object to associate with server. |
| `shutoff_timestamp` | `typing.Optional` | — | — | Timestamp of when server will shut down. |
| `sshkey` | `typing.Optional` | — | — | SSH key of the server |
| `tags` | `typing.Optional` | — | — | Optional field used for attaching specific firewall rules to machine |
| `state` | `typing.Optional` | — | — | Current build state of server |
| `state_timestamp` | `typing.Optional` | — | — | Timestamp of the server state |

<details><summary>JSON Schema</summary>

```json
{
  "$defs": {
    "FirewallRuleModel": {
      "properties": {
        "name": {
          "description": "Name of the firewall rule",
          "title": "Name",
          "type": "string"
        },
        "network": {
          "description": "Network of the firewall rule",
          "title": "Network",
          "type": "string"
        },
        "action": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Action of the firewall rule",
          "title": "Action"
        },
        "target_tags": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "title": "Target Tags"
        },
        "protocol": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Protocol of the firewall rule",
          "title": "Protocol"
        },
        "ports": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of ports to apply rule to.",
          "title": "Ports"
        },
        "ip_ranges": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": [
            "0.0.0.0/0"
          ],
          "description": "Range of source or destination IPs to attach rule to.",
          "title": "Ip Ranges"
        },
        "direction": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "INGRESS",
          "description": "Direction of flow of traffic.",
          "title": "Direction"
        },
        "priority": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 1000,
          "description": "Rule priority.",
          "title": "Priority"
        }
      },
      "required": [
        "name",
        "network"
      ],
      "title": "FirewallRuleModel",
      "type": "object"
    },
    "HumanInteractionModel": {
      "properties": {
        "display": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "title": "Display"
        },
        "protocol": {
          "description": "Protocol of the human interaction",
          "title": "Protocol",
          "type": "string"
        },
        "username": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Username"
        },
        "password": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Password"
        },
        "ssh_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ssh Key"
        },
        "domain": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Domain"
        },
        "security_mode": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "nla",
          "description": "Security mode of the human interaction",
          "title": "Security Mode"
        }
      },
      "required": [
        "protocol"
      ],
      "title": "HumanInteractionModel",
      "type": "object"
    },
    "NicModel": {
      "properties": {
        "network": {
          "description": "Network of the NIC",
          "title": "Network",
          "type": "string"
        },
        "internal_ip": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Internal IP of the NIC",
          "title": "Internal Ip"
        },
        "subnet_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": "default",
          "description": "Subnet name of the NIC",
          "title": "Subnet Name"
        },
        "external_nat": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Must be true if servers on network are intended to communicate outside of network.",
          "title": "External Nat"
        },
        "ip_aliases": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Assign multiple IP values to NIC.",
          "title": "Ip Aliases"
        },
        "direct_connect": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": false,
          "description": "Allow users to connect without using a proxy-machine.",
          "title": "Direct Connect"
        }
      },
      "required": [
        "network"
      ],
      "title": "NicModel",
      "type": "object"
    },
    "ServerDetailsModel": {
      "properties": {
        "description": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Useful services and programs this image is providing related to the workout.",
          "title": "Description"
        },
        "os": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Operating system of the server",
          "title": "Os"
        },
        "labels": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "List of services and functionality provided on this server.",
          "title": "Labels"
        }
      },
      "title": "ServerDetailsModel",
      "type": "object"
    }
  },
  "description": "Servers used as part of a Unit or Unit Workout lab.\nPartially based on information stored in AgogeImageModel objects.",
  "properties": {
    "add_disk": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": 0,
      "description": "Additional disk space of the server",
      "title": "Add Disk"
    },
    "build_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Build type of the server",
      "title": "Build Type"
    },
    "can_ip_forward": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether IP forwarding is enabled",
      "title": "Can Ip Forward"
    },
    "community_server": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether this server should be a shared server in a community build unit.",
      "title": "Community Server"
    },
    "details": {
      "anyOf": [
        {
          "$ref": "#/$defs/ServerDetailsModel"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "firewall_rules": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/FirewallRuleModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "List of firewall rules associated with server.",
      "title": "Firewall Rules"
    },
    "hidden": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether to display this server to students or not.",
      "title": "Hidden"
    },
    "human_interaction": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/HumanInteractionModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Human Interaction"
    },
    "hostname": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Public DNS record associated with server.",
      "title": "Hostname"
    },
    "image": {
      "description": "Image of the server",
      "title": "Image",
      "type": "string"
    },
    "machine_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "e1-standard1",
      "description": "Machine type of the server",
      "title": "Machine Type"
    },
    "metadata": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Metadata of the server",
      "title": "Metadata"
    },
    "guacamole_startup_script": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional startup script for Guacamole service",
      "title": "Guacamole Startup Script"
    },
    "startup_scripts": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional startup scripts to pass into server",
      "title": "Startup Scripts"
    },
    "min_cpu_platform": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "",
      "description": "Minimum CPU platform of the server",
      "title": "Min Cpu Platform"
    },
    "name": {
      "description": "Name of server.",
      "title": "Name",
      "type": "string"
    },
    "nics": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/NicModel"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Nics"
    },
    "parent_build_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Build type of parent object (i.e. workout, unit, etc.).",
      "title": "Parent Build Type"
    },
    "parent_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "ID of parent object to associate with server.",
      "title": "Parent Id"
    },
    "shutoff_timestamp": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Timestamp of when server will shut down.",
      "title": "Shutoff Timestamp"
    },
    "sshkey": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "SSH key of the server",
      "title": "Sshkey"
    },
    "tags": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional field used for attaching specific firewall rules to machine",
      "title": "Tags"
    },
    "state": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Current build state of server",
      "title": "State"
    },
    "state_timestamp": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Timestamp of the server state",
      "title": "State Timestamp"
    }
  },
  "required": [
    "image",
    "name"
  ],
  "title": "ServerModel",
  "type": "object"
}
```
</details>

## `StandardMappingsModel`

**Qualified name:** `common.models.agoge.StandardMappingsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `framework` | `str` | ✔️ | — | Framework of the standard mapping |
| `mapping` | `str` | ✔️ | — | Mapping of the standard |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "framework": {
      "description": "Framework of the standard mapping",
      "title": "Framework",
      "type": "string"
    },
    "mapping": {
      "description": "Mapping of the standard",
      "title": "Mapping",
      "type": "string"
    }
  },
  "required": [
    "framework",
    "mapping"
  ],
  "title": "StandardMappingsModel",
  "type": "object"
}
```
</details>

## `SubNetworkModel`

**Qualified name:** `common.models.agoge.SubNetworkModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Name of the subnetwork |
| `ip_subnet` | `str` | ✔️ | — | IP subnet of the subnetwork |
| `promiscuous_mode` | `typing.Optional` | — | `False` | Toggle promiscuous mode for this subnetwork |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "description": "Name of the subnetwork",
      "title": "Name",
      "type": "string"
    },
    "ip_subnet": {
      "description": "IP subnet of the subnetwork",
      "title": "Ip Subnet",
      "type": "string"
    },
    "promiscuous_mode": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Toggle promiscuous mode for this subnetwork",
      "title": "Promiscuous Mode"
    }
  },
  "required": [
    "name",
    "ip_subnet"
  ],
  "title": "SubNetworkModel",
  "type": "object"
}
```
</details>

## `TeachingConceptsModel`

**Qualified name:** `common.models.agoge.TeachingConceptsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `id` | `str` | ✔️ | — | ID of the teaching concept |
| `name` | `str` | ✔️ | — | Name of the teaching concept |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "description": "ID of the teaching concept",
      "title": "Id",
      "type": "string"
    },
    "name": {
      "description": "Name of the teaching concept",
      "title": "Name",
      "type": "string"
    }
  },
  "required": [
    "id",
    "name"
  ],
  "title": "TeachingConceptsModel",
  "type": "object"
}
```
</details>

## `WebApplicationModel`

**Qualified name:** `common.models.agoge.WebApplicationModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `name` | `str` | ✔️ | — | Display name of the container |
| `host_name` | `str` | ✔️ | — | Host name for the URL |
| `starting_directory` | `str` | ✔️ | — | The starting web directory for the container URL. |
| `url` | `typing.Optional` | — | — | Full path of web application |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "description": "Display name of the container",
      "title": "Name",
      "type": "string"
    },
    "host_name": {
      "description": "Host name for the URL",
      "title": "Host Name",
      "type": "string"
    },
    "starting_directory": {
      "description": "The starting web directory for the container URL.",
      "title": "Starting Directory",
      "type": "string"
    },
    "url": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Full path of web application",
      "title": "Url"
    }
  },
  "required": [
    "name",
    "host_name",
    "starting_directory"
  ],
  "title": "WebApplicationModel",
  "type": "object"
}
```
</details>

## `WorkspaceSettingsModel`

**Qualified name:** `common.models.agoge.WorkspaceSettingsModel`

| Field | Type | Required | Default | Description |
|------:|------|:-------:|---------|-------------|
| `count` | `int` | ✔️ | — | The number of distinct workstation builds to deploy |
| `registration_required` | `typing.Optional` | — | `False` | Whether students must login to access this build |
| `student_emails` | `typing.Optional` | — | — | Email addresses of students when registration is required |
| `student_names` | `typing.Optional` | — | — | Name of the student assigned to the workspaces |
| `expires` | `float` | ✔️ | — | UTC timestamp of date when resources are available until. |

<details><summary>JSON Schema</summary>

```json
{
  "properties": {
    "count": {
      "description": "The number of distinct workstation builds to deploy",
      "title": "Count",
      "type": "integer"
    },
    "registration_required": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": false,
      "description": "Whether students must login to access this build",
      "title": "Registration Required"
    },
    "student_emails": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Email addresses of students when registration is required",
      "title": "Student Emails"
    },
    "student_names": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Name of the student assigned to the workspaces",
      "title": "Student Names"
    },
    "expires": {
      "description": "UTC timestamp of date when resources are available until.",
      "title": "Expires",
      "type": "number"
    }
  },
  "required": [
    "count",
    "expires"
  ],
  "title": "WorkspaceSettingsModel",
  "type": "object"
}
```
</details>

