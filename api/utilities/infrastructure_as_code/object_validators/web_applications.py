from common.models.agoge import WebApplicationModel


class WebApplicationsValidator:
    def __init__(
        self,
        config: dict
    ) -> None:
        self.config = config

    def load(self) -> dict:
        for web_app in self.config['web_applications']:
            WebApplicationModel(**web_app)
        return self.config
