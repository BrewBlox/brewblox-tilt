import argparse
import json
import shlex
import sys


def parse_cmd_args(raw_args: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--name')
    parser.add_argument('--debug', action='store_true')

    parser.add_argument('--mqtt-protocol')
    parser.add_argument('--mqtt-host')
    parser.add_argument('--mqtt-port')

    parser.add_argument('--history-topic')
    parser.add_argument('--state-topic')

    parser.add_argument('--lower-bound')
    parser.add_argument('--upper-bound')
    parser.add_argument('--scan-duration')
    parser.add_argument('--active-scan-interval')
    parser.add_argument('--inactive-scan-interval')
    parser.add_argument('--simulate', nargs='*')

    return parser.parse_known_args(raw_args)


if __name__ == '__main__':
    args, unknown = parse_cmd_args(sys.argv[1:])
    if unknown:
        print(f'WARNING: ignoring unknown CMD arguments: {unknown}', file=sys.stderr)
    output = [f'brewblox_tilt_{k}={shlex.quote(str(v))}'
              for k, v in vars(args).items()
              if v is not None
              and v is not False
              and k != 'simulate']
    print(*output, sep='\n')

    # Special exception for list variables
    if args.simulate:
        sim_names = json.dumps(list(args.simulate))
        print(f"brewblox_tilt_simulate='{sim_names}'")
