from enum import Enum


class Buckets:
    BUILD_SPEC_BUCKET_SUFFIX = "build-specs"
    MARKDOWN_BUCKET_SUFFIX = 'markdown-images'

    class Folders(str, Enum):
        SPECS = "specs/"
        ATTACKS = 'attacks/'
        STARTUP_SCRIPTS = "startup_scripts/"
        TEACHER_FOLDER = "teacher_instructions/"
        STUDENT_FOLDER = "student_instructions/"
        IMAGES_FOLDER = 'markdown_images/'
