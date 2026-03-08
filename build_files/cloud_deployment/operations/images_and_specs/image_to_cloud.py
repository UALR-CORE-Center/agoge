from local_to_cloud import LocalToCloud
from image_from_cloud import ImageFromCloud
from message import Message


class ImageSource:
    LOCAL = 'local'
    CLOUD = 'cloud'


class ImageToCloud:
    def __init__(self):
        self.image_class = None
        self.message = Message()

    def run(self) -> None:
        self.message.info("[Import Image to Cloud]")
        while True:
            self.message.default("Select import image source")
            opts = [
                f"[0] {ImageSource.LOCAL} (Virtual Machine to upload to cloud)",
                f"[1] {ImageSource.CLOUD} (Virtual Machine created in authorized cloud project)"
            ]
            for source in opts:
                self.message.default(source, indent=True)

            image_source = str(input(f"Image Source: "))
            if image_source == '0':
                self.image_class = LocalToCloud()
                break
            elif image_source == '1':
                self.image_class = ImageFromCloud()
                break

        self.image_class.run()


if __name__ == '__main__':
    ImageToCloud().run()
