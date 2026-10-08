# pyMountOperator


A simple package to facillitate communication with a indi-compatible mount through pyindi-client.

`MountOperator` covers what a node needs: `connect` / `disconnect` (sets `DEVICE_PORT` and the
baud rate when the driver has them), `unpark` / `park`, `set_tracking`, `move_coord` (slew to
RA/Dec, then track; or SLEW / SYNC), `get_EOD_COORD`, `guide` (timed guide pulses),
`move_dir` with `set_slew_speed`, `go_home`, and the abort calls. All of it is tested against
`indi_simulator_telescope`; `uv run pytest` runs the unit tests without a server.




### Setup

- create a venv, and activate it with python3 and source. Then, use pip to install 

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -Ur requirements.txt
```

or in fish shell 
```fish
python3 -m venv .venv
source .venv/bin/activate.fish
pip install -Ur requirements.txt
```


- if you ever add a new package, ensure that you add it into requirements.txt using the following commands:

```bash
pip freeze > requirements.txt
```

this ensures that we maintain a universal package list across various computers, and that no one has to spend time figuring out what package was added by the other guy.


### Running the program
- To run the demo (main.py), you need to have indiserver installed. Search it up for your OS, and install it. Then try the following commands below

in a new window

```bash
indiserver -v indi_ioptronv3_telescope
```

and in your project, with the environment activated (source .venv/bin.activate)

```bash
python3 main.py
```

### Documentation

- Documentation is done through Sphinx. See [Sphinx's Documentation](https://www.sphinx-doc.org/en/master/index.html) for more information on how to do this. As long as you stick to the proper formatting when documenting your functions, classes, variables, etc, there should be no issue with sphinx detecting it.

- to build documentation FOR THIS SPECIFIC PROJECT:

ensure that all dependencies are installed from requirements.txt

```bash
cd docs
sphinx-apidoc -o ./source/api ../.
make clean
make latexpdf
```
latexpdf generates a pdf document using latex, and the doc will be located in '_build/latex/'. Ensure you have all dependencies for latex installed for it to work. if you can't use latex, try building an epub or html instead.

> You will have to run `sphinx-apidoc` in the docs folder each time you add or delete source files.

> To view full project documentation, refer to PolyOculusDocs

## Formatting

- use Ruff for formatting python. [See Ruff](https://docs.astral.sh/ruff/formatter/)

### Things that are complete
- below is a list of features that are complete
    - connecting with indiserver 
    - basic documentation
 - Below is a list of features that are in progress
    - Connecting to the device (Mount)
        - recieving a stream of RA and Dec coordinates (where the mount is pointed) 
        - arbitrary move commands (e.x. move until I say stop)

### Things that are in progress


### Things to add
- below is a list of features that have yet to be completed. These are listed in order of priority.
    - basic testing with pytests
    - error handling for all our functions
  - Coordinate move commands (e.x. move to a specific RA and Dec)
  - sending complex move commands
  -  pulse guide commands (more special than the other move commands because it requires changing the slew rate as we approach the target. This ensures a higher accuracy, and that we reach it properly)
- backlash compensation in case it is not already handled by the mount or driver [see this link from wikipedia to see what I mean](https://en.wikipedia.org/wiki/Backlash_(engineering))
