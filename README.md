# {Project Name}

### Usage
##### Installing dependencies in a virtual environment
```
$ sudo apt-get install build-essential python-dev python-pip python-virtualenv
$ virtualenv --no-site-packages venv
$ . ./venv/bin/activate
$ pip install tornado bidict pycrypto enum
```

##### Run 4 components in separate terminals
```
# start a distributed network relay
$ . ./venv/bin/activate
$ python voters/relay.py 10000 10001
```

```
# start a voter
$ . ./venv/bin/activate
$ python voters/voter.py 127.0.0.1 10000 1
```

```
# start a defender 
$ . ./venv/bin/activate
$ python defender.py
```

```
# start a challenger 
$ . ./venv/bin/activate
$ python challenger.py
```
