from cloud_fn_utilities.gcp.image_manager import ImageManager
from cloud_fn_utilities.gcp.cloud_env import CloudEnv

env_dict = CloudEnv().get_env()


def create(name: str):
    im = ImageManager(name=name, env_dict=env_dict)
    im.create_production_image()


def check_in(name: str):
    im = ImageManager(name=name, env_dict=env_dict)
    im.check_in()


def check_out(name: str):
    im = ImageManager(name=name, env_dict=env_dict)
    im.check_out()


def start(name: str):
    im = ImageManager(name=name, env_dict=env_dict)
    im.start_server()


def stop(name: str):
    im = ImageManager(name=name, env_dict=env_dict)
    im.stop_server()


if __name__ == "__main__":
    print(f"Compute Image Tester.")
    name = 'csec3314-powershell'
    check_out(name)
    print('complete')
