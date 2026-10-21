"""Run the local demo or validate a configuration without contacting devices."""
import argparse
from .config import load
from .server import Application


def main():
    parser = argparse.ArgumentParser(description='NOCtv community edition')
    parser.add_argument('command', choices=['serve', 'check'], nargs='?', default='serve')
    parser.add_argument('--config', default='config/demo.json')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    if args.command == 'check':
        load(args.config)
        print('Configuration valid; no upstream connections made.')
        return
    from wsgiref.simple_server import make_server
    app = Application(args.config)
    print(f'NOCtv local preview: http://{args.host}:{args.port}', flush=True)
    try:
        with make_server(args.host, args.port, app) as server:
            server.serve_forever()
    finally:
        app.collector.stop.set()


if __name__ == '__main__':
    main()
