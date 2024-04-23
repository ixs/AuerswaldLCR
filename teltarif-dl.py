#!/usr/bin/env python3
"""
Teltarif LCR Downloader
Download teltarif LCR data and build an Auerswald LCR XML Table.

Author: Andreas Thienemann
License: GPLv3+
"""

import argparse
import hashlib
import logging
import os
import os.path
import requests
import yaml
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from decimal import Decimal


class TeltarifLCRDownloader:
    def __init__(self, config=None, verbose=0, quiet=False, logger=None) -> None:
        self._load_config(config)
        self.max_alternatives = 3
        self.verbose = verbose
        self.html_parser = "lxml"
        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
            "Referer": "https://www.teltarif.de/tarife/call-by-call/",
        }
        self.base_url = (
            "https://www.teltarif.de/tarife/call-by-call/{country}/{network}/"
        )
        self.base_params = {
            "gssico": 75,
            "gssic": 7,
            "gseino": 75,
            "gsein": 7,
        }
        self.base_params_unused = {
            "zs": "flat",
            "ech": 0,
            "cbc": 0,
            "ctr": 0,
            "clb": 0,
            "pre": 1,
            "rou": 0,
            "eig": 0,
            "ansage": 255,
            "zugang": 4,
            "umsatz": 0,
            "grundgeb": 0,
            "c1": 0,
            "c2": 1,
        }
        self.testing = False

        self.logger = logger or logging.getLogger(__name__)
        log_level = logging.DEBUG if self.verbose > 0 else logging.INFO
        log_level = logging.ERROR if quiet else log_level
        self.logger.setLevel(log_level)

    def _load_config(self, file=None) -> None:
        if not file:
            file = f"{self.script_dir}/lcr.yaml"
        with open(file, "rb") as f:
            self.config = yaml.safe_load(f)

    def fetch_table(self, country, network, region=False):
        """Download the table from Teltarif, optionally using cache"""
        name = f"{country}_{network}"
        url = self.base_url.format(country=country, network=network)

        # Special case usa, there is no "festnetz" network, just the bare country url
        if country == "usa" and network == "festnetz":
            url = "https://www.teltarif.de/tarife/call-by-call/usa/"

        if region:
            name += f"_{region}"
            url += f"{region}/"

        if not os.path.exists(f"{self.script_dir}/cache"):
            os.makedirs(f"{self.script_dir}/cache")
        if self.testing and os.path.exists(f"{self.script_dir}/cache/{name}.html"):
            self.logger.debug(f"Using cached cache/{name}.html")
            with open(f"{self.script_dir}/cache/{name}.html", "r") as f:
                r = f.read()
        else:
            self.logger.debug(f"Downloading {url}")
            r = self.session.get(url, params=self.base_params).text
            with open(f"{self.script_dir}/cache/{name}.html", "w") as f:
                f.write(r)

        return r

    def parse_html_overview(self, input):
        """Detect the parser to use"""
        soup = BeautifulSoup(input, features=self.html_parser)
        table = soup.find("table", id="erg_table")
        if table.find("th", id="jetztgueltig"):
            # simple table found
            return self.parse_html_overview_simple(input)
        elif "Netzzugang" in [x.text for x in table.find_all("th")]:
            # complex table found
            return self.parse_html_overview_complex(input)

    def parse_html_overview_simple(self, input):
        """Parse the "simple" html page and extract data"""

        results = {"providers": {}}

        soup = BeautifulSoup(input, features=self.html_parser)
        table = soup.find("table", id="erg_table")

        # Get the table footer with the update time
        table_foot = soup.find("div", class_="tabfuss")
        results["updated_at"] = (
            table_foot.find("div", class_="fr").text.split(":", 1)[1].strip()
        )
        # Notes and prefixes have no id, but are right after the footer.
        notes = table_foot.find_next_sibling("div")
        prefixes = notes.find_next_sibling("div")
        results["notes"] = [
            x.replace("\n", " ") for x in list(notes.stripped_strings)[1:]
        ]
        results["prefixes"] = prefixes.text.split(":", 1)[1].strip().split(", ")

        times = []
        for cell in table.find_all("th"):
            slot = cell.text.strip().splitlines()[0]
            times.append(slot)
            self.logger.debug("Found timeslot %s", slot)
            results["providers"].update({slot: []})

        # Get data rows, skip the first row as it is non-data.
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            ranking = (
                int(list(cells[0].strings)[1].strip())
                if len(list(cells[0].strings)) == 3
                else int(list(cells[0].strings)[2].strip())
            )
            self.logger.debug("Found entry with rank %d", ranking)

            for idx in range(len(times)):
                data = list(cells[idx + 1].stripped_strings)
                self.logger.debug("Extracted text for provider: %s", data)
                product_url = cells[idx + 1].find("a").attrs["href"]
                price = data[0].replace("\xa0", " ")
                pulse = (
                    "60/60"
                    if "Alle Tarife haben den Takt 60/60" in results["notes"]
                    else None
                )
                if "Alle Tarife heißen Call by Call" in results["notes"]:
                    product = "Call by Call"
                else:
                    product = data.pop()
                prefix = data[-2]
                provider = data[-1]
                parsed = {
                    "rank": ranking,
                    "provider": provider,
                    "product": product,
                    "prefix": prefix,
                    "price": price,
                    "pulse": pulse,
                    "provider_url": None,
                    "product_url": product_url,
                }
                self.logger.debug("Parsed entry as %s", parsed)
                results["providers"][times[idx]].append(parsed)
        return results

    def parse_html_overview_complex(self, input):
        """Parse the "simple" html page and extract data"""

        slot = "Mo-So ganztags"
        results = {"providers": {slot: []}}

        soup = BeautifulSoup(input, features="html.parser")
        table = soup.find("table", id="erg_table")

        # Get the table footer with the update time
        table_foot = soup.find("div", class_="tabfuss")
        results["updated_at"] = (
            table_foot.find("div", class_="fr").text.split(":", 1)[1].strip()
        )
        # Notes and prefixes have no id, but are right after the footer.
        prefixes = table_foot.find_next_sibling("div")
        results["prefixes"] = prefixes.text.split(":", 1)[1].strip().split(", ")

        # Get data rows, skip the first row as it is non-data.
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            ranking = (
                int(list(cells[0].strings)[2].strip())
                if len(list(cells[0].strings)) == 4
                else int(list(cells[0].strings)[3].strip())
            )
            price = cells[1].text.replace("\xa0", " ")
            pulse = cells[2].text
            provider = cells[3].text
            provider_url = cells[3].find("a").attrs["href"]
            product = cells[4].text
            product_url = cells[4].find("a").attrs["href"]
            notes = [
                x.strip()
                for x in cells[5].text.replace("\xa0", " ").split("-")
                if len(x.strip()) > 0
            ]
            prefix = cells[6].text

            results["providers"][slot].append(
                {
                    "rank": ranking,
                    "provider": provider,
                    "product": product,
                    "prefix": prefix,
                    "price": price,
                    "pulse": pulse,
                    "provider_url": provider_url,
                    "product_url": product_url,
                }
            )

        return results

    def fetch_all_tables(self):
        results = {}
        for dest in self.config["destinations"]:
            region = False
            tmp = [x.lower() for x in dest.split(maxsplit=1)]
            if isinstance(tmp, list) and len(tmp) == 2:
                country, network = tmp
                network = network[1:-1]
                if network not in ("festnetz", "mobilfunk"):
                    region = network
                    network = "festnetz"
            else:
                country = tmp[0]
                network = "festnetz"
            if network == "mobilfunk":
                network = "handy"
            country = country.replace("ß", "ss")
            country = country.replace("ä", "ae")
            country = country.replace("ö", "oe")
            country = country.replace("ü", "ue")
            if not isinstance(region, bool):
                region = region.replace(" ", "-")
            page = self.fetch_table(country, network, region)
            table = self.parse_html_overview(page)
            name = f"{country}_{network}"
            if region:
                name += f"_{region}"
            with open(f"{self.script_dir}/cache/{name}.yaml", "w") as f:
                f.write(yaml.dump(table))
            results.update({dest: table})
        return results

    def build_xml(self, input):
        """Build the XML table

        Notes: id lengths: Provider: 4, Netz: 4, Gasse: 4, DynRouting: 4, RoutingEntry: 5
        """
        root = ET.Element("Slcr4TablesDB")

        slcrProvider_table = ET.SubElement(root, "SlcrProvider_table")
        for entry in sorted(
            self.get_providers(input), key=lambda x: int(x["providerId"])
        ):
            slcrProvider = ET.SubElement(
                slcrProvider_table,
                "SlcrProvider",
                providerId=entry["providerId"],
                vorwahl=entry["vorwahl"],
                name=entry["name"],
            )

        slcrNetz_table = ET.SubElement(root, "SlcrNetz_table")
        for entry in sorted(self.get_networks(), key=lambda x: int(x["netzId"])):
            slcrNetz = ET.SubElement(
                slcrNetz_table, "SlcrNetz", netzId=entry["netzId"], name=entry["name"]
            )

        slcrGasse_table = ET.SubElement(root, "SlcrGasse_table")
        for entry in sorted(
            self.get_ranges(input) + self.get_exceptions(),
            key=lambda x: int(x["gassenId"]),
        ):
            slcrGasse = ET.SubElement(
                slcrGasse_table,
                "SlcrGasse",
                gassenId=entry["gassenId"],
                gasse=entry["gasse"],
                name=entry["name"],
                netzId=entry["netzId"],
                category=entry["category"],
            )

        slots, entries = self.get_slots(input)
        slcrDynRouting_table = ET.SubElement(root, "SlcrDynRouting_table")
        for entry in sorted(slots, key=lambda x: int(x["dynRoutingId"])):
            slcrDynRouting = ET.SubElement(
                slcrDynRouting_table,
                "SlcrDynRouting",
                dynRoutingId=entry["dynRoutingId"],
                netzId=entry["netzId"],
                tag=entry["tag"],
                schaltStunde=entry["schaltStunde"],
                schaltMinute=entry["schaltMinute"],
            )

        slcrRoutingEntry_table = ET.SubElement(root, "SlcrRoutingEntry_table")
        for entry in sorted(entries, key=lambda x: int(x["routingEntryId"])):
            slcrRoutingEntry = ET.SubElement(
                slcrRoutingEntry_table,
                "SlcrRoutingEntry",
                routingEntryId=entry["routingEntryId"],
                parentType=entry["parentType"],
                parentId=entry["parentId"],
                prio=entry["prio"],
                routingType=entry["routingType"],
                routingId=entry["routingId"],
                preisProMinute=entry["preisProMinute"],
                preisProVerbg=entry["preisProVerbg"],
                taktErster=entry["taktErster"],
                taktWeiterer=entry["taktWeiterer"],
            )

        tree = ET.ElementTree(root)

        # Sanity check
        counts = {}
        for table in ["Provider", "Netz", "Gasse", "DynRouting", "RoutingEntry"]:
            counts.update(
                {table: len(list(locals().get("slcr" + table + "_table", [])))}
            )
        for k, l in counts.items():
            m = self.config["limits"].get(k)
            if m and l > m:
                self.logger.error(
                    f"Error: {k}-Table maximum number of entries exceeded. {l} > {m}"
                )
                exit(2)

        try:
            ET.indent(tree, space="", level=0)
        except AttributeError:
            # Older xml.etree do not have indent support.
            pass
        try:
            return (
                ET.tostring(
                    root,
                    encoding="unicode",
                    xml_declaration=True,
                    method="xml",
                    short_empty_elements=False,
                ),
                counts,
            )
        except TypeError:
            return ET.tostring(root, encoding="unicode", method="xml"), counts

    def get_slots(self, input):
        """Get all routes

        Tages codes:
        31: Mo-Fr
        32: Sa
        192: So, Feiertag
        224: Sa-So
        255: Mo-So, Feiertag

        Routing types:
        0: kein lcr
        1: besetzt
        2: lcr
        """
        grouped_slots = {}
        entries = []
        for dest, data in input.items():
            for slot, prov in data["providers"].items():
                for p in prov:
                    if p["rank"] > self.max_alternatives:
                        break
                    if slot.startswith("Mo-Fr"):
                        day = 31
                    elif slot.startswith("Mo-So"):
                        day = 255
                    elif slot.startswith("Sa, So"):
                        day = 224
                    else:
                        raise RuntimeError(f"Unrecognized slot day definition {slot}")
                    if slot.endswith("ganztags"):
                        hour = "0"
                    elif slot.endswith(" Uhr"):
                        time = slot.rsplit(None, maxsplit=2)[1]
                        hour = time.split("-")[0]
                    else:
                        raise RuntimeError(f"Unrecognized slot time definition {slot}")

                    # Pull minutes from the hour or set to 00
                    if ":" in hour:
                        hour, minute = hour.split(":")
                    else:
                        minute = 0
                    netzId = self.generate_numeric_id(dest)
                    slot_id = self.generate_numeric_id(
                        f"{netzId},{dest},{day},{hour},{minute}"
                    )
                    # only _one_ provider needed
                    if p["rank"] <= 1:
                        grouped_slots.setdefault((netzId, day), []).append(
                            {
                                "dynRoutingId": slot_id,
                                "netzId": netzId,
                                "tag": str(day),
                                "schaltStunde": str(hour),
                                "schaltMinute": str(minute),
                            }
                        )

                    provider_name = p["provider"]
                    if p["product"]:
                        provider_name += f" {p['product']}"
                    entry_id = self.generate_numeric_id(
                        f"{slot_id},{self.generate_numeric_id(provider_name)},{p['rank']}",
                        5,
                    )
                    entries.append(
                        {
                            "routingEntryId": entry_id,
                            "parentType": "1",
                            "parentId": str(slot_id),
                            "prio": str(p["rank"]),
                            "routingType": "2",
                            "routingId": self.generate_numeric_id(provider_name, 4),
                            "preisProMinute": str(
                                int(
                                    Decimal(
                                        p["price"]
                                        .rsplit(maxsplit=2)[-2]
                                        .replace(",", ".")
                                    )
                                    * 100
                                )
                            ),
                            "preisProVerbg": str(0),
                            "taktErster": p["pulse"].split("/")[0],
                            "taktWeiterer": p["pulse"].split("/")[1],
                        }
                    )

        slots = []
        # Iterate over slots filling in the 00:00 switch if not already present
        for sg in [
            sorted(sublist, key=lambda x: int(x["schaltStunde"]))
            for sublist in list(grouped_slots.values())
        ]:
            # First slot is not at 00:00, need to add last slot again as 00:00 starting time.
            first_slot = sg[0]
            new_entries = []
            if int(first_slot["schaltStunde"]) > 0:
                last_slot = sg[-1]
                slot_id = self.generate_numeric_id(
                    f"{last_slot['netzId']},{last_slot['tag']},0,0", 4
                )
                slots.append(
                    {
                        "dynRoutingId": slot_id,
                        "netzId": last_slot["netzId"],
                        "tag": last_slot["tag"],
                        "schaltStunde": "0",
                        "schaltMinute": "0",
                    }
                )

                # copy the entries from the last slot to the newly created id
                for e in entries:
                    if e["parentId"] == last_slot["dynRoutingId"]:
                        entry_id = self.generate_numeric_id(
                            f"{slot_id},{e['prio']},{e['parentId']},{e['routingId']}", 5
                        )
                        new_element = e.copy()
                        new_element.update(
                            {
                                "routingEntryId": entry_id,
                                "parentId": slot_id,
                            }
                        )
                        new_entries.append(new_element)

            slots.extend(sg)
            entries.extend(new_entries)

        # Add RoutingEntry elements for the blacklisted routes
        for exception in self.get_exceptions():
            entry_id = self.generate_numeric_id(
                f"{exception['gasse']},{exception['name']}", 5
            )
            # We only need prio 3 for blacklist numbers
            for prio in [3]:
                entries.append(
                    {
                        "routingEntryId": entry_id,
                        "parentType": "0",
                        "parentId": str(exception["gassenId"]),
                        "prio": str(prio),
                        "routingType": "0",
                        "routingId": "0",
                        "preisProMinute": "0",
                        "preisProVerbg": "0",
                        "taktErster": "60",
                        "taktWeiterer": "60",
                    }
                )

        return slots, entries

    def get_exceptions(self):
        """Get all exceptions"""
        exceptions = []
        for prefix, desc in self.config["blacklist"].items():
            exceptions.append(
                {
                    "gassenId": self.generate_numeric_id(prefix),
                    "gasse": prefix,
                    "name": desc,
                    "netzId": "0",
                    "category": "1",
                }
            )
        return exceptions

    def get_ranges(self, input):
        """Get all number ranges"""
        ranges = []
        for dest, data in input.items():
            for prefix in data["prefixes"]:
                ranges.append(
                    {
                        "gassenId": self.generate_numeric_id(prefix),
                        "gasse": prefix,
                        "name": dest,
                        "netzId": self.generate_numeric_id(dest),
                        "category": "0",
                    }
                )
        return ranges

    def get_providers(self, input):
        """Get all providers"""
        providers = []
        # Just used to track duplicates
        provider_names = set()
        for dest, data in input.items():
            for slot, prov in data["providers"].items():
                for p in prov:
                    if p["rank"] > self.max_alternatives:
                        break
                    name = p["provider"]
                    if p["product"]:
                        name += f" {p['product']}"
                    if name in provider_names:
                        continue
                    provider_names.add(name)
                    providers.append(
                        {
                            "providerId": self.generate_numeric_id(name),
                            "vorwahl": p["prefix"],
                            "name": name,
                        }
                    )
        return list(providers)

    def get_networks(self):
        """Get all networks"""
        networks = []
        for dest in self.config["destinations"]:
            networks.append({"name": dest, "netzId": self.generate_numeric_id(dest)})
        return networks

    def generate_numeric_id(self, name, length=4):
        hex_digest = hashlib.sha256(name.encode()).hexdigest()
        numeric_id = int(hex_digest, 16) % (10 ** length)  # Ensure we're in length
        return str(numeric_id)


def main():
    parser = argparse.ArgumentParser(description="Teltarif LCR Downloader")

    parser.add_argument("output_file", help="Output file (mandatory)")
    parser.add_argument("--config", help="Config file (optional)")
    parser.add_argument("--test", action="store_true", help="Enable test mode")
    parser.add_argument("--quiet", action="store_true", help="Quiet mode, only errors")
    parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="Increase verbosity level"
    )

    args = parser.parse_args()

    # Set up logging
    log_format = "%(levelname)s: %(message)s"
    log_level = logging.DEBUG if args.verbose > 0 else logging.INFO
    logging.basicConfig(level=log_level, format=log_format)
    logger = logging.getLogger(__name__)
    quiet = False
    if args.output_file == "-" or args.quiet:
        logger.setLevel(logging.ERROR)
        quiet = True

    tt = TeltarifLCRDownloader(
        config=args.config, verbose=args.verbose, quiet=quiet, logger=logger
    )
    if args.test:
        logger.info(
            "Enabling test-mode, no downloads will be done, cached data used instead."
        )
    tt.testing = args.test
    results = tt.fetch_all_tables()
    xml, counts = tt.build_xml(results)
    if args.output_file == "-":
        print(xml)
    else:
        with open(args.output_file, "w") as f:
            f.write(xml)
        logger.info(f"LCR Data written to {args.output_file}.")
    for k, v in counts.items():
        logger.info(f"{v} {k}_table entries")


if __name__ == "__main__":
    main()
