Lightning Bitcoin 

light weight wallet

=====================================

Licence: MIT Licence

=======================================

Lightning Bitcoin light weight wallet is forked from [Electrum](https://github.com/spesmilo/electrum) v3.0.5

NOW Getting started

===============

For Windows users,


you can download latest release [here](http://downloadwallet.lbtc.io/index.php/s/HvkFNyCqVu3oc0r/downloads).


If you  use Linux, read the following:

> **NOTE :  All the following command work well on Ubuntu 16.04**

Check out the code from Github:
```
git clone git://github.com/lbtcio/lbtc-lightwallet-client

cd lbtc-lightwallet-client
```
Run install (this should install dependencies):
```




python3 setup.py install
```

Compile the icons file for Qt:
```

sudo apt-get install pyqt5-dev-tools

pyrcc5 icons.qrc -o gui/qt/icons_rc.py
```

Compile the protobuf description file:
```

sudo apt-get install protobuf-compiler

protoc --proto_path=lib/ --python_out=lib/ lib/paymentrequest.proto
```

Create translations (optional):
```

sudo apt-get install python-pycurl gettext

./contrib/make_locale

```
//=========//




Author
===============

**Benjamin Smith**

sunshine.benjamin.smith@gmail.com

1ECSDWsm17fbCECgdb5MvR3EZMT6Sbd232
