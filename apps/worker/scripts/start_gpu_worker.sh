#!/usr/bin/env bash
set -euo pipefail

prepend_if_dir() {
  local target_var="$1"
  local path="$2"
  if [[ -d "$path" ]]; then
    local current="${!target_var:-}"
    if [[ -n "$current" ]]; then
      export "$target_var=$path:$current"
    else
      export "$target_var=$path"
    fi
  fi
}

# Common OTB Python binding locations across OTB/OTBTF images.
prepend_if_dir PYTHONPATH /usr/local/lib/otb/python
prepend_if_dir PYTHONPATH /usr/lib/otb/python
prepend_if_dir PYTHONPATH /opt/otb/lib/otb/python
prepend_if_dir PYTHONPATH /opt/otbtf/lib/otb/python
prepend_if_dir PYTHONPATH /usr/lib/python3/dist-packages
prepend_if_dir PYTHONPATH /usr/local/lib/python3/dist-packages

# OTB application plugin locations.
prepend_if_dir OTB_APPLICATION_PATH /usr/local/lib/otb/applications
prepend_if_dir OTB_APPLICATION_PATH /usr/lib/otb/applications
prepend_if_dir OTB_APPLICATION_PATH /opt/otb/lib/otb/applications
prepend_if_dir OTB_APPLICATION_PATH /opt/otbtf/lib/otb/applications

# Shared library lookup locations.
prepend_if_dir LD_LIBRARY_PATH /usr/local/lib/otb
prepend_if_dir LD_LIBRARY_PATH /usr/lib/otb
prepend_if_dir LD_LIBRARY_PATH /opt/otb/lib/otb
prepend_if_dir LD_LIBRARY_PATH /opt/otbtf/lib/otb

if ! python3 -c "import otbApplication" >/dev/null 2>&1; then
  echo "ERROR: otbApplication Python module is unavailable in worker-gpu runtime." >&2
  echo "PYTHONPATH=${PYTHONPATH:-}" >&2
  echo "OTB_APPLICATION_PATH=${OTB_APPLICATION_PATH:-}" >&2
  exit 1
fi

exec celery -A worker.celery_app.celery_app worker -Q sr_gpu -l info --concurrency=1
