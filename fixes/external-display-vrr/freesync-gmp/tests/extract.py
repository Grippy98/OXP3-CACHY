#!/usr/bin/env python3
"""Extract prototype and original AMD functions verbatim for host sanitizer tests."""
import hashlib, pathlib, re, sys
root=pathlib.Path(__file__).resolve().parent.parent
out=pathlib.Path(sys.argv[1])
def extract(text,name):
 m=re.search(r'(?m)^(?:static\s+)?(?:void|bool)\s+'+re.escape(name)+r'\s*\([^;]*?\)\s*\{',text)
 if not m: raise RuntimeError(name)
 pos=m.end(); depth=1
 while depth:
  if text[pos]=='{': depth+=1
  elif text[pos]=='}': depth-=1
  pos+=1
 return text[m.start():pos]
src=root/'tests/fixtures/intel_dp.c'
names=['intel_dp_pcon_vrr_capable','intel_dp_pcon_freesync_v2_range','intel_dp_pcon_freesync_sdp_pack','intel_dp_is_pcon_freesync_sdp','intel_dp_pcon_freesync_is_sdr','intel_dp_compute_pcon_freesync_sdp']
text=src.read_text(); generated='/* Actual prototype functions, extracted verbatim. */\n'+'\n\n'.join(extract(text,n) for n in names)
amd=(root/'tests/amd_reference.c').read_text()
generated+='\n/* Original AMD functions, copied verbatim from candidate kernel. */\n'+amd
out.write_text(generated)
print(hashlib.sha256(src.read_bytes()).hexdigest(),src)
