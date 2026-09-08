from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists, NotFound
from google.pubsub_v1.services.publisher.pagers import ListTopicsPager

from .cloud_env import CloudEnv
from .cloud_logger import Logger, LoggerNames
from ...constants.pub_sub import PubSub


class PubSubManager:
    def __init__(
        self,
        topic: PubSub.Topics,
        log_name: str = LoggerNames.CLOUD_FN,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.logger = Logger(log_name=log_name)
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        self.topic_path = self.publisher.topic_path(self.env.project, topic.value)

    def create_topic(self) -> None:
        try:
            response = self.publisher.create_topic(request={"name": self.topic_path})
            self.logger.info(f'{self.class_name}:{self.topic_path} - Created topic:\n{response}')
        except AlreadyExists:
            self.logger.warning(f'{self.class_name}:{self.topic_path} - Topic already exists!')

    def delete_topic(self) -> bool:
        self.logger.info(f'{self.class_name}:{self.topic_path} - Deleting topic')
        try:
            self.publisher.delete_topic(request={'topic': self.topic_path})
            return True
        except NotFound:
            self.logger.info(f'{self.class_name}:{self.topic_path} - Topic not found!')
            return False

    def list_topics(self) -> ListTopicsPager:
        project_path = f'projects/{self.env.project}'
        return self.publisher.list_topics(request={"project": project_path})

    def create_subscription(self, subscription_id) -> None:
        subscription_path = self.subscriber.subscription_path(self.env.project, subscription_id)
        with self.subscriber:
            subscription = self.subscriber.create_subscription(
                request={"name": subscription_path, "topic": self.topic_path}
            )

    def delete_subscription(self, subscription_id) -> bool:
        subscription_path = self.subscriber.subscription_path(self.env.project, subscription_id)
        with self.subscriber:
            try:
                self.subscriber.delete_subscription(request={'subscription': subscription_path})
                return True
            except NotFound:
                self.logger.info(f'{self.class_name}:{subscription_id} - Subscription not found!')
                return False

    def msg(self, **args) -> pubsub_v1.publisher.futures.Future:
        str_attrs = {k: str(v) for k, v in args.items() if v is not None}
        return self.publisher.publish(
            self.topic_path,
            data=b'Agoge PubSub Message',
            **str_attrs,
        )
