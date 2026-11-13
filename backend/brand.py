"""The one place that names the product. Rename the app, change the publisher or bump the version here only.

Never change DATA_KEY or APP_ID after the first release: they keep the user's data folder and the installer's
upgrade/uninstall working even when the display name changes."""
import json

NAME = "Zighost"                       # shown to people (placeholder name, may change)
VERSION = "0.1.0"                      # stays 0.1.0 until the owner says otherwise
PUBLISHER = "shubverser"               # brand / publisher
PUBLISHER_NAME = "Shubham Keshri"      # legal person behind the publisher
COPYRIGHT = "© 2026 Shubham Keshri"
SUPPORT_EMAIL = "zighost.support@gmail.com"   # privacy questions, bug reports, data requests
POLICY_VERSION = 1                     # raise when the privacy policy changes in a way people must accept again
TAGLINE = "Host Minecraft servers on your own PC."

DATA_KEY = "zighost"                   # data folder name and instance id: NEVER change
APP_ID = "{272662F5-A911-4EA9-BC1E-3977AC6C1356}"   # installer id: NEVER change
API_HEADER = "X-MCPanel"               # internal request header, not shown to people

USER_AGENT = f"{NAME}/{VERSION}"
CLAIM_NAME = f"{NAME.lower()}-{VERSION}"            # name playit shows on its "Claim agent" page

# playit tunnels made by this app start with one of these. New ones use the first; older prefixes are still recognised.
TUNNEL_PREFIXES = (f"{NAME} ", "MC Panel ")


def public() -> dict:
    """What the browser may know."""
    return {"name": NAME, "version": VERSION, "publisher": PUBLISHER, "publisherName": PUBLISHER_NAME,
            "copyright": COPYRIGHT, "tagline": TAGLINE, "supportEmail": SUPPORT_EMAIL, "policyVersion": POLICY_VERSION, "dataKey": DATA_KEY}


def js() -> str:
    return "window.BRAND = " + json.dumps(public()) + ";\n"
