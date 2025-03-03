import http.client
import http.cookies
import json
import base64
import hashlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

"""
Copyright - FuseTim 2024

This code is dual-licensed under both the MIT License and the Apache License 2.0.

You may choose either license to govern your use of this code.

MIT License:
https://opensource.org/licenses/MIT

Apache License 2.0:
https://www.apache.org/licenses/LICENSE-2.0

By contributing to this project, you agree that your contributions will be licensed under 
both the MIT License and the Apache License 2.0.
"""

######################################################################################

# Credentials (found in Headers and Cookies)
auth_server = "------" # See `x-pm-uid` header
auth_token  = "------" # See `AUTH-<x-pm-uid>` cookie
session_id  = "------" # See `Session-Id` cookie
web_app_version = "web-vpn-settings@5.0.2.0" # See `x-pm-appversion` header

# Settings
prefix = "PREFIX" # Prefix is used for config file and name in ProtonVPN Dashboard
output_dir = "./" 
selected_countries = ["CH"]
selected_tier = 2 # 0 = Free, 2 = Plus
selected_features = [ ] # Features that a server should have ("P2P", "TOR", "SecureCore", "XOR", etc) or not ("-P2P", etc)
max_servers = 2 # Maximum of generated config
listing_only = False # Do not generate config, just list available servers with previous selectors

config_features = {
    "SafeMode": False,
    "SplitTCP": True,
    "PortForwarding": True,
    "RandomNAT": False,
    "NetShieldLevel": 0, # 0, 1 or 2 
};
######################################################################################

# Contants
connection = http.client.HTTPSConnection("account.protonvpn.com")
C = http.cookies.SimpleCookie()
C["AUTH-"+auth_server] = auth_token
C["Session-Id"] = session_id
headers = {
    "x-pm-appversion": web_app_version,
    "x-pm-uid": auth_server,
    "Accept": "application/vnd.protonmail.v1+json",
    "Cookie": C.output(attrs=[],header="", sep="; ")
}


def generateKeys():
    """Generate a client key-pair using the API. Could be generated offline but need more work..."""
    print("Generating key-pair...")
    connection.request("GET", "/api/vpn/v1/certificate/key/EC", headers=headers)
    response = connection.getresponse()
    print("Status: {} and reason: {}".format(response.status, response.reason))
    resp = json.loads(response.read().decode())
    priv = resp["PrivateKey"].split("\n")[1]
    pub = resp["PublicKey"].split("\n")[1]
    print("Key generated:")
    print("priv:", priv)
    print("pub:", pub)
    return [resp["PrivateKey"], pub, priv]


def getPubPEM(priv):
    """Return the Public key as string without headers"""
    return priv[1]

def getPrivPEM(priv):
    """Return the Private key as PKCS#8 without headers"""
    return priv[2]

def getPrivx25519(priv):
    """Return the x25519 base64-encoded private key, to be used in Wireguard config."""
    hash__ = hashlib.sha512(base64.b64decode(priv[2])[-32:]).digest()
    hash_ = list(hash__)[:32]
    hash_[0] &= 0xf8
    hash_[31] &= 0x7f
    hash_[31] |= 0x40
    new_priv = base64.b64encode(bytes(hash_)).decode()
    return new_priv


def registerConfig(server, priv):
    """Register a Wireguard configuration and return its raw response."""
    h = headers.copy()
    h["Content-Type"]= "application/json"
    print("Registering Config for server", server["Name"],"...")
    body = {
	"ClientPublicKey": getPubPEM(priv),
	"Mode": "persistent",
	"DeviceName": prefix+"-"+server["Name"],
	"Features": {
		"peerName": server["Name"],
		"peerIp": server["Servers"][0]["EntryIP"],
		"peerPublicKey": server["Servers"][0]["X25519PublicKey"],
		"platform": "Windows",
                # You can add features there (PortForwarding, SplitTCP, ModerateNAT
                # See https://github.com/ProtonMail/WebClients/blob/8b5035d6f848b76d005814fca260bb616e83a4b2/packages/components/containers/vpn/WireGuardConfigurationSection/feature.ts#L53
                "SafeMode": config_features["SafeMode"],
                "SplitTCP": config_features["SplitTCP"],
                "PortForwarding": config_features["PortForwarding"] if server["Features"] & 4 == 4 else False,
                "RandomNAT": config_features["RandomNAT"],
                "NetShieldLevel": config_features["NetShieldLevel"], # 0, 1 or 2 
	}
    }
    connection.request("POST", "/api/vpn/v1/certificate", body=json.dumps(body), headers=h)
    response = connection.getresponse()
    print("Status: {} and reason: {}".format(response.status, response.reason))
    resp = json.loads(response.read().decode())
    print(resp)
    return resp

def generateConfig(priv, register): 
    """Generate a Wireguard config using the ProtonVPN API answer."""
    conf = """[Interface]
# Key for {prefix}
PrivateKey = {priv}
Address = 10.2.0.2/32
DNS = 10.2.0.1

[Peer]
# {server_name}
PublicKey = {server_pub}
AllowedIPs = 0.0.0.0/0
Endpoint = {server_endpoint}:51820
    """.format(prefix=prefix, priv=getPrivx25519(priv), server_name=register["Features"]["peerName"], server_pub=register["Features"]["peerPublicKey"], server_endpoint=register["Features"]["peerIp"])
    return conf


def write_config_to_disk(name, conf):
    f = open(output_dir+"/"+name+".conf", "w")
    f.write(conf)
    f.close()


# VPN Listings

connection.request("GET", "/api/vpn/logicals", headers=headers)
response = connection.getresponse()
print("Status: {} and reason: {}".format(response.status, response.reason))

servers = json.loads(response.read().decode())["LogicalServers"]

for s in servers:
    feat = [
    "SecureCore" if s["Features"] & 1 == 1 else "-SecureCore",
    "TOR" if s["Features"] & 2 == 2 else "-TOR",
    "P2P" if s["Features"] & 4 == 4 else "-P2P",
    "XOR" if s["Features"] & 8 == 8 else "-XOR",
    "IPv6" if s["Features"] & 16 == 16 else "-IPv6"
    ]
    if (not s["EntryCountry"] in selected_countries and not s["ExitCountry"] in selected_countries) or s["Tier"] != selected_tier:
        continue
    if len(list(filter(lambda sf: not (sf in feat), selected_features))) > 0:
        continue
    print("- Server", s["Name"])
    print("  > ID:", s["ID"])
    print("  > EntryCountry:", s["EntryCountry"])
    print("  > ExitCountry:", s["ExitCountry"])
    print("  > Tier:", s["Tier"])
    print("  > Features:")
    print("      - SecureCore:", "Y" if s["Features"] & 1 == 1 else "N")
    print("      - Tor:", "Y" if s["Features"] & 2 == 2 else "N")
    print("      - P2P:", "Y" if s["Features"] & 4 == 4 else "N")
    print("      - XOR:", "Y" if s["Features"] & 8 == 8 else "N")
    print("      - IPv6:", "Y" if s["Features"] & 16 == 16 else "N")
    print("  > Score:", s["Score"])
    print("  > Load:", s["Load"])
    print("  > Status:", s["Status"])
    print("  > Instance:")
    for i in s["Servers"]:
        print("    - Instance n°",i["Label"],":", i["ID"])
        print("      > EntryIP:", i["EntryIP"])
        print("      > ExitIP:", i["ExitIP"])
        print("      > Domain:", i["Domain"])
        print("      > X25519PublicKey:", i["X25519PublicKey"])
    if not listing_only:
        keys = generateKeys()
        reg = registerConfig(s, keys)
        config = generateConfig(keys, reg)
        write_config_to_disk(reg["DeviceName"], config)
        max_servers-=1
    if (max_servers <= 0):
        break

connection.close()
