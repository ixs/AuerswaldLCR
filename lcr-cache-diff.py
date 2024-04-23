#!/usr/bin/env python3

import os
import yaml
import logging
import argparse

def compare_yaml_files(dir1, dir2):
    logger = logging.getLogger(__name__)

    # Get the list of YAML files in both directories
    yaml_files1 = [file for file in os.listdir(dir1) if file.endswith('.yaml')]
    yaml_files2 = [file for file in os.listdir(dir2) if file.endswith('.yaml')]
    all_files = set(yaml_files1 + yaml_files2)

    for file in all_files:
        path1 = os.path.join(dir1, file)
        path2 = os.path.join(dir2, file)

        if file not in yaml_files1:
            logger.debug("Skipping non-YAML file: %s", file)
            continue

        if file not in yaml_files2:
            logger.warning("File '%s' exists in '%s' but not in '%s'", file, dir1, dir2)
            continue

        with open(path1, 'r') as f1, open(path2, 'r') as f2:
            data1 = yaml.safe_load(f1)
            data2 = yaml.safe_load(f2)

        logger.debug("Comparing file: %s", file)
        compare_dicts(data1, data2, logger)

def compare_dicts(dict1, dict2, logger, path=""):
    for key in dict1.keys() | dict2.keys():
        value1 = dict1.get(key)
        value2 = dict2.get(key)

        if isinstance(value1, dict) and isinstance(value2, dict):
            compare_dicts(value1, value2, logger, path + "/" + str(key))
        elif isinstance(value1, list) and isinstance(value2, list):
            if len(value1) != len(value2):
                logger.info("Difference in %s: Length of lists %s and %s differs", path, value1, value2)
            else:
                for i, (item1, item2) in enumerate(zip(value1, value2)):
                    if isinstance(item1, dict) and isinstance(item2, dict):
                        compare_dicts(item1, item2, logger, path + "/" + str(key) + f"[{i}]")
                    elif item1 != item2:
                        logger.info("Difference in %s: %s[%d] -> %s vs %s", path, key, i, item1, item2)
        elif value1 != value2:
            logger.info("Difference in %s: %s -> %s vs %s", path, key, value1, value2)



def main():
    parser = argparse.ArgumentParser(description='Compare YAML files in two directories')
    parser.add_argument('dir1', help='Directory 1 path')
    parser.add_argument('dir2', help='Directory 2 path')
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

    compare_yaml_files(args.dir1, args.dir2)

if __name__ == "__main__":
    main()
