"""myCUVAS portal logo (gold cap + white "myCUVAS" on indigo banner).

PNG 2172x724, stored as base64 text in mycuvas_logo_part01..12.py
because the GitHub push path rejects binary files (each part file is
under 128KB). The bytes are a LOSSLESS PIL re-encode (optimize=True,
compress_level=9) of the user-supplied file; decoded pixels are
identical to the original (same 2172x724 dimensions, same raw pixel
md5 490a9fb94de6302a00bfb9e4c4683773). Original upload md5:
b5ed47f9f64222eab26641c48384e4fe. Pixels never cropped, stretched,
recoloured, or lossy-compressed. Served by the /brand/mycuvas-logo.png
route in app.py. The official CUVAS logo (brand_logo.py) is untouched
and still serves the home page.
"""

import os

_PARTS = ["mycuvas_logo_part%02d" % i for i in range(1, 13)]


def _load():
    import importlib.util

    here = os.path.dirname(os.path.abspath(__file__))
    chunks = []
    for name in _PARTS:
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(here, name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        chunks.append(mod.CHUNK)
    return "".join(chunks)


MYCUVAS_LOGO_B64 = _load()
