"""myCUVAS portal logo (gold cap + white "myCUVAS" on indigo banner).

PNG 2172x724, stored as base64 text in mycuvas_logo_part01..12.py
because the GitHub push path rejects binary files (each part file is
under 128KB). The bytes are a LOSSLESS PNG re-encode (PIL optimize=True,
compress_level=9) of the DECODED PIXELS of the user-supplied WebP file
(workspace/user/media_library/image/81/81925ae285c728ed6b35449adfce604b93b666c36b63695c0130654985c250db.webp,
md5 a5ad6b485bfa0e4c05ab97e1bcb6b70c); decoded pixels are identical
to that WebP's decoded pixels (same 2172x724 dimensions, same raw pixel
md5 ff28d23560126e6eb40487098245428a). This REPLACED the previous
myCUVAS logo — no bytes of the old logo remain. Pixels never cropped, stretched,
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
