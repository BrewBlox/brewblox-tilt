# Brewblox Service for the Tilt Hydrometer

The [Tilt hydrometer](https://tilthydrometer.com/) is a wireless hydrometer and thermometer used to gather live readings of specific gravity and temperature when brewing beer.

[Brewblox](https://brewblox.netlify.app) is a modular brewery control system design to work with the BrewPi Spark controller.

This service integrates the Tilt hydrometer into the Brewblox stack.
You only need a single service: it will track all Tilts in range.

## Credits

This service is a continuation of [James Sandford](https://github.com/j616)'s [Tilt service](https://github.com/j616/brewblox-tilt).

## Usage

### Install script

You can use the `brewblox-ctl` tool to add a new Tilt service to your system.
This will create the ./tilt directory, and edit your `docker-compose.yml` file.

```
brewblox-ctl add-tilt
```

### Or: Manually add the Tilt service to the Brewblox stack

You need to create the `~/brewblox/tilt` directory, and add the service to the `docker-compose.yml` file.

```bash
mkdir ~/brewblox/tilt
```

```yaml
  tilt:
    image: brewblox/brewblox-tilt:${BREWBLOX_RELEASE}
    restart: unless-stopped
    privileged: true
    network_mode: host
    volumes: ['./tilt:/share']
    labels: ['traefik.enable=false']
```

Finally, you'll have to bring up the new service using

```bash
brewblox-ctl up
```

### Running on a remote machine

On the remote machine in the directory you wish to install the service, create a `docker-compose.yml` file like this with the relevant IP address for the brewblox host.

```yaml
version: '3.7'
services:
  tilt:
    image: brewblox/brewblox-tilt:${BREWBLOX_RELEASE:-edge}
    restart: unless-stopped
    privileged: true
    network_mode: host
    volumes: ['./tilt:/share']
    command: --mqtt-host=<brewblox_hostname/IP>
```

Create the directory for the tilt files
```bash
mkdir tilt
```

Start the service with the following command
```bash
docker-compose up -d
```

### Configure ports

By default, the Tilt services uses MQTT over WSS (HTTPS websockets).

If you are using a non-default HTTPS port (e.g. if you run brewblox on a NAS), you'll also want to add `--mqtt-port=<port>` to the command.

### Add to your graphs

Once the Tilt service receives data from your Tilt(s), it should be available as graph metrics in Brewblox.

## Device names

Whenever a Tilt is detected, it is assigned a unique name.
The first Tilt of a given color will be named after the color.
If you have more than one Tilt of a single color, the name will be incremented.
For example, if you have three red Tilt devices, the names will be:
- Tilt
- Tilt-2
- Tilt-3

Device names can be edited in the Brewblox UI, or in the `~/brewblox/tilt/devices.yml` file.
If you edit the file, you must restart the service for the changes to take effect.

### Calibration

Calibration is optional. While the Tilt provides a good indication of fermentation progress without calibration, it's values can be less accurate than a traditional hydrometer. With calibration its accuracy is approximately that of a traditional hydrometer. If you wish to use your Tilt for anything beyond simple tracking of fermentation progress (e.g. stepping temperatures at a given SG value) it is recommended you calibrate your Tilt.

If you wish to calibrate your Specific Gravity readings, create a file called `SGCal.csv` in the `~/brewblox/tilt` directory with lines of the form:

```
<device name>, <uncalibrated_value>, <calibrated_value>
```

The device name is the name as described above. If a custom device name containing spaces is used, the name must be quoted.
The name is case-sensitive.

The uncalibrated values are the raw values from the Tilt. The calibrated values are those from a known good hydrometer or calculated when creating your calibration solution. Calibration solutions can be made by adding sugar/DME to water a little at a time to increase the SG of the solution. You can take readings using a hydrometer and the Tilt app as you go. You can include calibration values for multiple colours of Tilt in the calibration file. A typical calibration file would look something like this:

```
Black, 1.000, 1.001
Black, 1.001, 1.002
Black, 1.002, 1.003
Black, 1.003, 1.004
Red, 1.000, 1.010
Red, 1.001, 1.011
Red, 1.002, 1.012
Red, 1.003, 1.013
Red, 1.004, 1.014
```

You will need multiple calibration points. We recommend at least 6 distributed evenly across your typical gravity range for each Tilt. For example, if you usually brew with a starting gravity of 1.050, you may choose to calibrate at the values 1.000, 1.010, 1.020, 1.030, 1.040, 1.050, and 1.060. The more calibration points you have, the more accurate the calibrated values the service creates will be. Strange calibrated values from the service are an indication you have used too few or poorly distributed calibration values.

Calibration values for temperature are placed in a file called `tempCal.csv` in the `tilt` directory and have the same structure. Temperature values in the calibration file MUST be in Fahrenheit. The tempCal file can also contain calibration values for multiple Tilts. Again, it should contain at least 6 points distributed evenly across your typical range. A typical tempCal file would look like this:-

```
Black,39,40
Black,46,48
Black,54,55
Black,60,62
Black,68,70
Black,75,76
```

Calibrated values will be logged in Brewblox separately to uncalibrated values. If you don't provide calibration values for a given colour of Tilt, only uncalibrated values will be logged. You don't need to calibrate both temperature and SG. If you only want to provide calibration values for SG, that works fine. Calibrated temp values would not be generated in this case but calibrate SG values would.

It is also recommended that you re-calibrate SG whenever you change your battery. Different batteries and different placements of the sled inside the Tilt can affect the calibration.

## Limitations

As the Tilt does not talk directly to the Spark controller, you cannot use your Tilt to control the temperature of your system. This service currently only allows you to log values from the Tilt. To control your BrewPi/Brewblox setup you will need a BrewPi temperature sensor.

## Development

To get started:

Install [Pyenv](https://github.com/pyenv/pyenv):
```
sudo apt-get update -y && sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
xz-utils tk-dev libffi-dev liblzma-dev python-openssl git python3-venv python-is-python3

curl https://pyenv.run | bash
```

After installing, it may suggest to add initialization code to ~/.bashrc. Do that.

To apply the changes to ~/.bashrc (or ~/.zshrc), run:
```
exec $SHELL --login
```

Install Python 3.9
```bash
pyenv install 3.9.7
```

Install [Poetry](https://python-poetry.org/)
```
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python

exec $SHELL --login
```

Install Bluetooth dependencies
```bash
sudo apt install -y \
    libbluetooth-dev
```

Configure and install the environment used for this project.

**Run in the root of the cloned brewblox-tilt directory**
```bash
poetry run pip install --upgrade pip
poetry install
```

During development, you need to have your environment activated. When it is activated, your terminal prompt is prefixed with (.venv).

Visual Studio Code with suggested settings does this automatically whenever you open a .py file. If you prefer using a different editor, you can do it manually by running:
```bash
poetry shell
```

Install [Docker](https://www.docker.com/101-tutorial)
```
curl -sL get.docker.com | sh

sudo usermod -aG docker $USER

reboot
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
