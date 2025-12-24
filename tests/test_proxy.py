import requests

proxies = {
    "http": "socks5://127.0.0.1:9050",
    "https": "socks5://127.0.0.1:9050",
}

"""
proxies = {
    "http":  "socks5h://torproxy:9050",
    "https": "socks5h://torproxy:9050",
}
"""

print(requests.get("https://youtube.com", proxies=proxies).status_code)
# Expected output: 200