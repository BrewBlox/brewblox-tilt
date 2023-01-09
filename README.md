# Brewblox Service for the Tilt Hydrometer

**For usage documentation, see <https://www.brewblox.com/user/services/tilt.html>**

The [Tilt hydrometer](https://tilthydrometer.com/) is a wireless hydrometer and thermometer used to gather live readings of specific gravity and temperature when brewing beer.

[Brewblox](https://brewblox.com) is a modular brewery control system design to work with the BrewPi Spark controller.

This service integrates the Tilt hydrometer into the Brewblox stack.
You only need a single service: it will track all Tilts in range.

## Credits

This service is a continuation of [James Sandford](https://github.com/j616)'s [Tilt service](https://github.com/j616/brewblox-tilt).

## Development

To install pyenv + poetry, see the instructions at <https://github.com/BrewBlox/brewblox-boilerplate#readme>

You will also need Bluetooth support on the host to build the Python packages:

```bash
sudo apt update && sudo apt install -y libbluetooth-dev
```

To build a local Docker image:

```bash
bash docker/before_build.sh
docker build --tag brewblox/brewblox-tilt:local docker
```

A `docker-compose.yml` file that uses `brewblox/brewblox-tilt:local` is present in the repository root.

To start it, run:

```bash
docker-compose up -d
```
