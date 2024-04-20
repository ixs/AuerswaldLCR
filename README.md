# AuerswaldLCR

Update the Least-Cost-Router tables in an Auerswald PBX system.

Current Auerswald PBX system offer a least-cost-router that allows to route calls via various providers.

This is a client for the Soft-LCR 4.0 interface.

[Telefonsparbuch](http://www.telefonsparbuch.de) XML files are compatible and can be imported into the PBX.  
This has been tested with the [AuerswaldVOIP](http://www.telefonsparbuch.de/tmpl/calc/telephone/lcr/AuerswaldVoIP/calc_tk.htm)
type.

## Installation

Clone the repo, install the requirements using pip:

```
git clone https://github.com/ixs/AuerswaldLCR.git
cd AuerswaldLCR
pip install -r requirements.txt
```

## Configuration

Rename `auerswald.cfg.yaml.sample` to `auerswald.cfg.yaml` and add your site specific details.

## Usage

`./auerswald-lcr.py --help` for help output.  
`./auerswald-lcr.py download [filename]` to download the LCR XML from the PBX.  
`./auerswald-lcr.py --pretty download [filename]` to download the LCR XML from the PBX and prettify it.  
`./auerswald-lcr.py upload [filename]` to upload a LCR XML to the PBX.  
`./auerswald-lcr.py defaults` to reset the LCR XML back to defaults.  
`./auerswald-lcr.py erase` flush all LCR tables on the PBX.

In case of trouble, the `--debug` option will enable logging of all data sent over the wire.
