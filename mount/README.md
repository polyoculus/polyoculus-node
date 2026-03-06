# pyMountOperator


a simple package to allow interfacing with any iOptron mount, utilizing their RS232 Mount Command Language, and connecting through serial.




### Installation

- create a venv, and activate it with python3 and source. Then, use pip to install 

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -Ur requirements.txt
```



- if you ever add a new package, ensure that you add it into requirements.txt using the following commands:

```bash
pip freeze > requirements.txt
```

this ensures that we maintain a universal package list across various computers, and that no one has to spend time figuring out what package was added by the other guy.


### Documentation

- Documentation is done through Sphinx. See [Sphinx's Documentation](https://www.sphinx-doc.org/en/master/index.html) for more information on how to do this. As long as you stick to the proper formatting when documenting your functions, classes, variables, etc, there should be no issue with sphinx detecting it.
