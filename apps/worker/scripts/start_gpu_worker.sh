#!/usr/bin/env bash
set -euo pipefail

prepend_if_dir() {
  local target_var="$1"
  local path="$2"
  if [[ -d "$path" ]]; then
    local current="${!target_var:-}"
    case ":$current:" in
      *":$path:"*) return 0 ;;
    esac
    if [[ -n "$current" ]]; then
      export "$target_var=$path:$current"
      return 0
    fi
    export "$target_var=$path"
  fi
}

# Common OTB Python binding locations across OTB/OTBTF images.
prepend_if_dir PYTHONPATH /usr/local/lib/otb/python
prepend_if_dir PYTHONPATH /usr/lib/otb/python
prepend_if_dir PYTHONPATH /opt/otb/lib/otb/python
prepend_if_dir PYTHONPATH /opt/otbtf/lib/otb/python

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

if ! python3 - <<'PY'
import os
import sys
import traceback

try:
    import numpy
    print(f"INFO: numpy {numpy.__version__} from {numpy.__file__}")
    import otbApplication
    print(f"INFO: otbApplication from {otbApplication.__file__}")
except Exception:
    print("ERROR: otbApplication Python module is unavailable in worker-gpu runtime.", file=sys.stderr)
    print(f"PYTHONPATH={os.environ.get('PYTHONPATH', '')}", file=sys.stderr)
    print(f"OTB_APPLICATION_PATH={os.environ.get('OTB_APPLICATION_PATH', '')}", file=sys.stderr)
    traceback.print_exc()
    raise SystemExit(1)
PY
then
  exit 1
fi

exec celery -A worker.celery_app.celery_app worker -Q sr_gpu -l info --concurrency=1
