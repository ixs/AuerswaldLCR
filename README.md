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

# TeltarifLCRDownloader

A small tool to download LCR data from [teltarif.de](www.teltarif.de) and build an Auerswald-readable
XML file for the least cost router.
As it looks like Telefon-Sparbuch is not updating anymore, this might come in handy.

_Usage Note:_ Do not hammer the teltarif server with this.

```
./teltarif-dl.py --help
usage: teltarif-dl.py [-h] [--config CONFIG] [--test] [--verbose] output_file

Teltarif LCR Downloader

positional arguments:
  output_file      Output file (mandatory)

options:
  -h, --help       show this help message and exit
  --config CONFIG  Config file (optional)
  --test           Enable test mode
  --verbose, -v    Increase verbosity level
```

The resulting file can easily be uploaded to the Auerswald PBX system.

# Automatic updater

`./update.sh` is a script to automate the updating of the LCR tables.  
This can be called from cron or similar.

# LCR Cache Differ

`./lcr-cache-diff.py` can be used to diff the YAML files from two different
cache directories to spot differences in the underlying LCR data.

Perfect for trying to understand what changed between downloader runs.
