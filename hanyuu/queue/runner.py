from __future__ import absolute_import
import argparse
import json

from . import server


def jsonfile(filename):
    with open(filename, 'r') as f:
        return json.load(f)


parser = argparse.ArgumentParser(description="Start a JSON RPC server based queue.")
parser.add_argument('--config', '-c', help="location of configuration file", type=jsonfile)

parser.add_argument('--host', help="address to bind server listener on.", default="localhost", type=unicode)
parser.add_argument('--port', help="port to use for the server listener.", default=9999, type=int)
parser.add_argument('--backend', help="queue storage backend to use.", default="mysql", type=unicode)

def main():
    args = parser.parse_args()

    server.run_server(args.host, args.port, args.backend, args.config)


if __name__ == "__main__":
    main()