export enum BuildType {
    AGENT_SERVER = 'agent',
    UNIT = "unit",
    WORKOUT = "workout",
    ESCAPE_ROOM = 'escape_room'
}

export enum AssessmentScriptLanguages {
    PYTHON = 'python',
    POWERSHELL = 'powershell',
    BASH = 'bash',
}

export enum UnitType {
    SOLO = 'solo',
    COMMUNITY = 'community'
}

export enum Frameworks {
    NICE = "NICE"
}

export enum TeachingConcepts {
    ETHICS = 'Ethics',
    ESTABLISHING_TRUST = 'Establishing Trust',
    UBIQUITOUS_COMPUTING = 'Ubiquitous Computing',
    DATA_SECURITY = 'Data Security',
    SYSTEM_SECURITY = 'System Security',
    ADVERSARIAL_THINKING = 'Adversarial Thinking',
    RISK = 'Risk',
    IMPLICATIONS = 'Implications',
    COURSES = 'Courses',
    TRAINING = 'Training',
    PREREQUISITES = 'Prerequisites',
    EVALUATION = 'Evaluation',
    EXERCISE = 'Exercise'
}

export function mapTeachingConcepts(tags: string[]): { id: string, name: string }[] {
    const conceptMap: { [key: string]: string } = {
        ETHICS: TeachingConcepts.ETHICS,
        ESTABLISHING_TRUST: TeachingConcepts.ESTABLISHING_TRUST,
        UBIQUITOUS_COMPUTING: TeachingConcepts.UBIQUITOUS_COMPUTING,
        DATA_SECURITY: TeachingConcepts.DATA_SECURITY,
        SYSTEM_SECURITY: TeachingConcepts.SYSTEM_SECURITY,
        ADVERSARIAL_THINKING: TeachingConcepts.ADVERSARIAL_THINKING,
        RISK: TeachingConcepts.RISK,
        IMPLICATIONS: TeachingConcepts.IMPLICATIONS,
        COURSES: TeachingConcepts.COURSES,
        TRAINING: TeachingConcepts.TRAINING,
        PREREQUISITES: TeachingConcepts.PREREQUISITES,
        EVALUATION: TeachingConcepts.EVALUATION,
        EXERCISE: TeachingConcepts.EXERCISE,
    };
    return tags.map(tag => ({ id: tag.toLowerCase(), name: conceptMap[tag] }));
}

export namespace Firewalls {
    export enum FirewallTypes {
        FORTINET = "fortinet",
        VYOS = "vyos",
        VPC = 'vpc'
    }

    export enum TransportProtocols {
        TCP = "tcp",
        UDP = "udp",
        ICMP = "icmp"
    }

    export enum TrafficDirection {
        INGRESS = 'INGRESS',
        EGRESS = 'EGRESS'
    }

    export enum Action {
        ALLOW = 'allow',
        DENY = 'deny'
    }
}

export namespace Networks {
    export namespace Reservations {
        export const DISPLAY_SERVER = '10.1.0.3';
        export const WORKSPACE_PROXY_SERVER = '10.1.0.4';
        export const WORKOUT_PROXY_SERVER = "10.1.1.3";
        export const FIXED_ARENA_WORKOUT_SERVER_RANGE: [string, string] = ['10.1.0.10', '10.1.0.200'];
        export const AGENT_MACHINE = '10.1.0.210';
    }
    export const GATEWAY_NETWORK_NAME = 'gateway';
    export const GATEWAY_NETWORK_CONFIG = {
        name: GATEWAY_NETWORK_NAME,
        subnets: [
            {
                name: 'default',
                ip_subnet: '10.1.0.0/24'
            }
        ]
    };
    export const WORKOUT_EXTERNAL_NAME = 'external';
}

export enum QuestionTypes {
    AUTO = "auto",
    INPUT = "input",
    UPLOAD = "upload"
}

export enum LMS {
    CANVAS = 'canvas',
    BLACKBOARD = 'blackboard',
    GOOGLE_CLASSROOM = 'classroom'
}

export enum LMSCourseWork {
    QUIZ = 'quiz',
    ASSIGNMENT = 'assignment'
}

export enum SpecSource {
    FILE = 'file',
    FORM = 'form'
}

export enum ImageScopes {
    PROJECT = 'project',
    GLOBAL = 'global'
}
