#!/bin/bash
#
# Update script
#
set -euo pipefail

script_dir=$(dirname "$0")

date=$(date +"%Y-%m-%d-%H:%M")

if [ ! -d "${script_dir}/venv" ]; then
	echo "venv not found, creating"
	python3 -m venv "${script_dir}/venv"
	"${script_dir}/venv/bin/pip" install -qq -r requirements.txt
	"${script_dir}/venv/bin/pip" install xmldiff
fi

mkdir "${script_dir}/cache" 2> /dev/null|| true
"${script_dir}/venv/bin/python3" \
	"${script_dir}/teltarif-dl.py" \
	--quiet "${script_dir}/cache/teltarif-${date}.xml"
"${script_dir}/venv/bin/python3" \
	"${script_dir}/auerswald-lcr.py" \
	download \
	"${script_dir}/cache/current-${date}.xml"

# Now do the actual check --check would be easier,
# but we do not have that on older releases...
if [ "$("${script_dir}/venv/bin/xmldiff" \
		"${script_dir}/cache/current-${date}.xml" \
		"${script_dir}/cache/teltarif-${date}.xml" | \
		grep -c '\[')" -eq "0" ]; then
	# File is the same, means no change, we can clean up
	rm -rf "${script_dir}/cache"
else
	# File is different than PBX, upload to PBX
	echo "LCR Tables differ, uploading new tables to PBX..."
	"${script_dir}/venv/bin/python3" \
		"${script_dir}/auerswald-lcr.py" \
		upload \
		"${script_dir}/cache/teltarif-${date}.xml"
	# Archive the cache for debugging
	tar -cz -f "${script_dir}/cache.tar.gz" -C "${script_dir}" ./cache
	mv "${script_dir}/cache.tar.gz" "${script_dir}/cache-${date}.tar.gz"
	rm -rf "${script_dir}/cache"
fi
