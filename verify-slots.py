#!/usr/bin/env python3

import os
import yaml
import logging
import argparse

def verify_slots(dir):
    logger = logging.getLogger(__name__)

    # Get the list of YAML files in both directories
    yaml_files = [file for file in os.listdir(dir) if file.endswith('.yaml')]
    for file in yaml_files:
        path = os.path.join(dir, file)
 
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        logger.debug("Comparing file: %s", file)
        print(list(data["providers"].keys()))



def main():
    parser = argparse.ArgumentParser(description='Compare YAML files in two directories')
    parser.add_argument('dir1', help='Directory 1 path')
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

    verify_slots(args.dir1)

if __name__ == "__main__":
    main()
