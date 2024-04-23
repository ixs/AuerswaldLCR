#!/usr/bin/env python3
"""
AuerswaldLCR
Update the Least-Cost-Router tables in an Auerswald PBX system

Author: Andreas Thienemann
License: GPLv3+
"""

import argparse
import os.path
import gzip
import requests
import urllib.parse
import logging
import xml.dom.minidom
import yaml


class AuerswaldLCR:
    """Auerswald LCR client"""

    def __init__(self):
        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.ssl_verify = False
        self.uuid = None
        self._load_config()
        self.session = requests.Session()
        self.session.auth = requests.auth.HTTPDigestAuth(
            self.auer_admin_user, self.auer_admin_pass
        )
        self.session.verify = False

        # Silence warnings if we're not doing verification
        if not self.ssl_verify:
            from requests.packages.urllib3.exceptions import InsecureRequestWarning

            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def _load_config(self):
        """Load the configfile"""
        file=f"{self.script_dir}/auerswald.cfg.yaml"
        with open(file, "r") as f:
            data = yaml.safe_load(f)
        self.auer_address = data["auer_address"]
        self.auer_admin_user = data["auer_admin_user"]
        self.auer_admin_pass = data["auer_admin_pass"]

    def _enable_debug(self):
        """Enable debug output for requests"""
        try:
            import http.client as http_client
        except ImportError:
            # Python 2
            import httplib as http_client
        http_client.HTTPConnection.debuglevel = 1

        # You must initialize logging, otherwise you'll not see debug output.
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    def _fetch(self, path):
        """Fetch generic data drom the PBX"""
        r = self.session.get(f"https://{self.auer_address}{path}")
        return r

    def _send(self, path, params=None, data=None, files=None, headers=None):
        """Post generic data to the PBX"""
        r = self.session.post(
            f"https://{self.auer_address}{path}",
            params=params,
            data=data,
            files=files,
            headers=headers,
        )
        return r

    def fetch_max_values(self):
        pass

    def fetch_lcr_table(self):
        """Fetch list of LCR tables"""
        return self._fetch("/lcr35tabellen_list").json()

    def fetch_lcr_provider(self):
        """Fetch list of LCR providers"""
        return self._fetch("/lcr35tabellen_provider").json()

    def fetch_lcr_networks(self):
        """Fetch list of LCR networks (Gasssen)"""
        return self._fetch("/lcr35netze_state").json()

    def fetch_lcr_table_info(self, netid, category, pageindex):
        """Fetch of LCR networks details"""
        params = {
            "netzid": netid,
            "category": category,
            "pageindex": pageindex,
        }
        return self._fetch("/lcr35tabellen_state", params=params).json()

    def download_lcr_xml(self):
        """Download the LCR Table XML Export"""
        return gzip.decompress(self._fetch("/lcr35datensicherung_export").content)

    def set_lcr_defaults(self):
        """Reset the LCR to defaults"""
        return self._send("/lcr35datensicherung_default")

    def upload_lcr_xml(self, filename, content):
        """Upload and import new LCR XML table"""
        url = "/lcr35datensicherung_import"
        params = {"h_ulfilename": filename}
        files = {"file": (filename, gzip.compress(content), "text/xml")}
        r = self._send(
            url,
            params=params,
            files=files,
            headers={
                "Content-Encoding": "gzip",
            },
        )
        return r.json()

    def erase_table(self, tbl):
        """Empty existing LCR tables"""
        tables = {
            "networks": "lcr35netze",
            "providers": "lcr35provider",
        }
        self.erase_single_lcr_table(path=f"/{tables[tbl]}")

    def erase_single_lcr_table(self, path):
        """Erase all entries from a single LCR table"""
        existing_data = self._fetch(f"{path}_state").json()
        path = f"{path}_save"
        data = {"ids": []}
        for e in existing_data["rows"]:
            id = e["id"]
            data["ids"].append(str(id))
            data[f"{id}_gr_id"] = id
            data[f"{id}_!nativeeditor_status"] = "deleted"
        data["ids"] = ",".join(data["ids"])
        return self._send(path, data=urllib.parse.urlencode(data, safe="!"))

    def download_xml(self, filename, pretty=False):
        """Cmdline handler for downloading XML"""
        xml_content = self.download_lcr_xml()
        with open(filename, "w") as f:
            if pretty:
                lcr = xml.dom.minidom.parseString(xml_content)
                # Write out the prettyfied version, we need to add a newline after the <?xml
                # header though.
                f.write(
                    lcr.toprettyxml(indent="  ", newl="").replace(
                        '<?xml version="1.0" ?>', '<?xml version="1.0" ?>\n'
                    )
                )
            else:
                f.write(xml_content.decode())

    def upload_xml(self, filename):
        """Cmdline handler for uploading XML"""
        with open(filename, "rb") as f:
            r = self.upload_lcr_xml(os.path.basename(filename), f.read())
        if len(r["errors"]) > 0:
            print("Error uploading XML")
            for e in r["errors"]:
                print(e["err_str"])
            exit(1)
        if len(r["warnings"]) > 0:
            print("Warning uploading XML")
            for w in r["warnings"]:
                print(w)
            exit(1)

    def main(self):
        parser = argparse.ArgumentParser(
            description="Update the Least-Cost-Router tables in an Auerswald PBX system"
        )
        parser.add_argument(
            "command",
            choices=["upload", "download", "defaults", "erase"],
            help="File handling, whether to upload or download the XML file.",
        )
        parser.add_argument("--debug", action="store_true", help="Debug output.")
        parser.add_argument(
            "--pretty", action="store_true", help="Prettify XML file when downloading."
        )
        parser.add_argument("filename", type=str, nargs="?", help="LCR XML file.")

        args = parser.parse_args()

        if args.debug:
            self._enable_debug()

        if args.command == "upload":
            if args.filename:
                self.upload_xml(args.filename)
            else:
                print("Error: Please provide a filename to upload.")
        elif args.command == "download":
            if args.filename:
                self.download_xml(args.filename, args.pretty)
            else:
                print("Error: Please provide a filename to download.")
        elif args.command == "defaults":
            self.set_lcr_defaults()
        elif args.command == "erase":
            for tbl in ["networks", "providers"]:
                self.erase_table(tbl)
        else:
            parser.print_help()


if __name__ == "__main__":
    aw_lcr = AuerswaldLCR()
    aw_lcr.main()
