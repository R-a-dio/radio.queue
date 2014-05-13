import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
      name="radio.queue",
      version="1.4.0a",
      author='Wessie',
      author_email='r-a-dio@wessie.info',
      description=("Queue RPC implementation."),
      license='GPL',
      install_requires=[
                  "jsonrpclib",
      ],
      extras_require={
          "mysql": ["mysql-python"],
      },
      entry_points={
          "console_scripts": [
              "radio.queue = radio.queue.runner:main",
          ],
      },
      keywords="streaming icecast fastcgi irc",
      packages=['radio', 'radio.queue'],
      )
