from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    To,
    From,
    Subject,
    Content
)
from common.constants.database import DatabaseTypes, DATABASE_NAME
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv
from .email_templates.templates import Templates


class SendMail:
    def __init__(
        self,
        env_dict: dict = None
    ) -> None:
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.sendgrid_api_key = self.env.sendgrid_api_key
        if not self.sendgrid_api_key:
            raise ValueError('sendgrid_api_key does not exist in project')
        self.sg = SendGridAPIClient(api_key=self.sendgrid_api_key)
        self.dns_suffix = self.env.dns_suffix

    def send_email(self, subject, to, content=None, attachment=None):
        message = Mail()
        message.from_email = From(
            email=f"no-reply@trojan-cybergym.org"  # {self.dns_suffix}"
        )
        message.subject = subject
        message.to = to
        if content:
            message.content = content
        if attachment:
            message.attachment = attachment
        try:
            response = self.sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e)

    def from_template(self, msg_subject, msg_to) -> None:
        # TODO: Replace this with support email
        message = Mail()
        message.from_email = From(email=f"no-reply@trojan-cybergym.org")
        message.subject = Subject(subject=msg_subject.value)
        message.content = Templates().get_template(msg_subject)
        message.to = msg_to
        try:
            response = self.sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e)

    def send_expiring_units(
        self,
        unit_id: str,
        workout_name: str,
        instructor: str,
        num_workouts: int,
        hours_until_expires: int
    ) -> None:
        """
        sends an email to the provided instructor's email that the unit is about to expire
        @return:
        """
        project = self.env_dict['project']
        eml_subject = Subject(f"Unit in {project} about to expire")
        eml_to = To(instructor)
        eml_content = Content(
            mime_type="text",
            content=f"Unit id: {unit_id}\n"
                    f"Name: {workout_name}\n"
                    f"Project: {project}\n"
                    f"Number of Workouts: {num_workouts}\n"
                    f"Expires in {hours_until_expires} hours\n"
        )
        self.send_email(subject=eml_subject, to=eml_to, content=eml_content)
