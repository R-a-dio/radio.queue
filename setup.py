import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
      name="hanyuu.queue",
      version="1.4.0a",
      author='Wessie',
      author_email='r-a-dio@wessie.info',
      description=("Queue RPC implementation for hanyuu."),
      license='GPL',
      install_requires=[
                  "jsonrpclib",
      ],
      extras_require={
          "mysql": ["mysql-python"],
      },
      entry_points={
          "console_scripts": [
              "hanyuu.queue = hanyuu.queue.runner:main",
          ],
      },
      keywords="streaming icecast fastcgi irc",
      packages=['hanyuu', 'hanyuu.queue'],
      )
