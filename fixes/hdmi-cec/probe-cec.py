#!/usr/bin/env python3
"""Read-only CEC-over-AUX capability report; run as root for DP AUX access."""
import datetime
import glob
import gzip
import json
import os
from pathlib import Path
import platform

result = {
    'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'kernel': platform.release(),
    'cec_devices': sorted(glob.glob('/dev/cec*')),
    'kernel_config': [],
    'ports': [],
    'writes_performed': False,
}
try:
    config = gzip.open('/proc/config.gz', 'rt').read().splitlines()
    wanted = ('CONFIG_CEC_CORE=', 'CONFIG_DRM_DISPLAY_DP_AUX_CEC=',
              'CONFIG_DRM_DISPLAY_DP_AUX_CHARDEV=', 'CONFIG_MEDIA_CEC_RC=',
              'CONFIG_USB_PULSE8_CEC=', '# CONFIG_USB_PULSE8_CEC ')
    result['kernel_config'] = [s for s in config if s.startswith(wanted)]
except OSError as error:
    result['kernel_config_error'] = str(error)
for aux in sorted(Path('/sys/class/drm_dp_aux_dev').glob('drm_dp_aux*')):
    connector = (aux / 'device').resolve()
    if '-DP-' not in connector.name:
        continue
    status = (connector / 'status').read_text().strip()
    if status != 'connected':
        continue
    port = {'connector': connector.name, 'aux': aux.name,
            'aux_name': (aux / 'name').read_text().strip(), 'status': status}
    try:
        fd = os.open('/dev/' + aux.name, os.O_RDONLY)
        try:
            for label, address, count in [
                ('receiver_capabilities', 0, 16),
                ('mst_capability', 0x21, 1),
                ('branch_identity', 0x500, 16),
                ('cec_capability_control', 0x3000, 4),
            ]:
                data = os.pread(fd, count, address)
                if len(data) != count:
                    raise OSError(f'short read at {address:#x}: {len(data)}/{count}')
                port[label] = data.hex()
            values = [os.pread(fd, 1, 0x3000) for _ in range(3)]
            if any(len(value) != 1 for value in values):
                raise OSError('short CEC capability read')
            port['cec_capability_repeat'] = [value.hex() for value in values]
            port['advertises_cec_tunneling'] = all(value[0] & 1 for value in values)
        finally:
            os.close(fd)
    except OSError as error:
        port['error'] = str(error)
    result['ports'].append(port)
print(json.dumps(result, indent=2))
