"""myCUVAS portal logo (gold cap + white "myCUVAS" on indigo banner).

PNG 2172x724 RGBA, stored as base64 text in mycuvas_logo_part01..12.py
because the GitHub push path rejects binary files (each part file is
under 128KB). The bytes are a LOSSLESS PNG re-encode (PIL optimize=True,
compress_level=9) of the DECODED RGBA PIXELS of the user-supplied WebP file
(workspace/user/media_library/image/b1/b16d9853c2aa6ed27c8b7399b1bdaccba0361c44c89cdfc92414cbfc8e75f8e5.webp,
md5 098d480c36ae34de8edd31986f13fd1d); decoded pixels are identical
to that WebP's decoded pixels (same 2172x724 dimensions, same raw RGBA pixel
md5 3097bd1caf0c36fea8a5e53efa503483). The alpha channel is PRESERVED
(RGBA mode, never flattened to RGB): all four corner pixels are fully
transparent (alpha 0), so the banner genuinely renders with rounded
corners on every background — the previous version had opaque black
corners and looked rectangular on white bands. This REPLACED the previous
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
