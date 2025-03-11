import json
import os
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import qbittorrentapi
import transmission_rpc

def get_config():
    return {
        "skip_check": os.environ.get("SKIP_CHECK", "true"),
        "qbittorrent": {
            "host": os.environ.get("QBITTORRENT_HOST", "localhost"),
            "port": int(os.environ.get("QBITTORRENT_PORT", "8080")),
            "username": os.environ.get("QBITTORRENT_USERNAME", "admin"),
            "password": os.environ.get("QBITTORRENT_PASSWORD", "adminadmin")
        },
        "transmission": {
            "protocol": os.environ.get("TRANSMISSION_PROTOCOL", "http"),
            "host": os.environ.get("TRANSMISSION_HOST", "localhost"),
            "port": int(os.environ.get("TRANSMISSION_PORT", "9091")),
            "path": os.environ.get("TRANSMISSION_PATH", "/transmission"),
            "username": os.environ.get("TRANSMISSION_USERNAME", ""),
            "password": os.environ.get("TRANSMISSION_PASSWORD", ""),
            "torrent_dir": os.environ.get("TRANSMISSION_TORRENT_DIR", "~/.config/transmission-daemon/torrents")
        }
    }

def main():
    # Get config
    if os.environ.get("ENVIRON_CONFIG"):
        config = get_config()
    else:
        config: dict = json.load(open('./config.json', 'r'))

    # Skip check or not.
    skip_check: bool = config['skip_check']

    # qBittorrent settings.
    qb_host: str = config['qbittorrent']['host']
    qb_port: int = config['qbittorrent']['port']
    qb_username: str | None = config['qbittorrent']['username'] or None
    qb_password: str | None = config['qbittorrent']['password'] or None

    # Transmission settings.
    tr_protocol: Literal['http', 'https'] = config['transmission']['protocol']
    tr_host: str = config['transmission']['host']
    tr_port: int = config['transmission']['port']
    tr_path: str = config['transmission']['path']
    tr_username: str | None = config['transmission']['username'] or None
    tr_password: str | None = config['transmission']['password'] or None
    tr_torrent_dir: str = config['transmission']['torrent_dir']

    # Connect qBittorrent.
    qb_client = qbittorrentapi.Client(
        host=qb_host,
        port=qb_port,
        username=qb_username,
        password=qb_password
    )

    # Check if login is successful.
    qb_client.auth_log_in()
    print(f"Connected to qBittorrent {qb_client.app.version}.")

    # Connect Transmission.
    tr_client = transmission_rpc.Client(
        protocol=tr_protocol,
        username=tr_username,
        password=tr_password,
        host=tr_host,
        port=tr_port,
        path=tr_path
    )

    # Check if login is successful.
    tr_session = tr_client.get_session()
    print(f"Connected to Transmission {tr_session.version}.")

    # Get all hashes of torrents in qBittorrent.
    qb_torrents = qb_client.torrents_info()
    qb_torrent_hashes: list[str] = [torrent.hash for torrent in qb_torrents]
    print(f"Found {len(qb_torrent_hashes)} torrents in qBittorrent.")

    # Get all torrents in Transmission.
    tr_torrents = tr_client.get_torrents()
    print(f"Fetched {len(tr_torrents)} torrents in Transmission. Transfer them to qBittorrent...")

    for tr_torrent in tr_torrents:
        # Pause the torrent in Transmission.
        tr_client.stop_torrent(tr_torrent.id)

        # Skip torrents that already exist in qBittorrent.
        if tr_torrent.hashString in qb_torrent_hashes:
            print(f"Torrent {tr_torrent.name} already exists in qBittorrent, skipping.")
            continue

        category: str = Path(tr_torrent.download_dir).name

        # Get torrent file path.
        tr_torrent_path = str(Path(tr_torrent_dir).expanduser().joinpath(tr_torrent.hashString + '.torrent').absolute())

        # Add torrent to qBittorrent.
        qb_client.torrents_add(
            torrent_files=open(tr_torrent_path, 'rb'),
            save_path=tr_torrent.download_dir,
            rename=tr_torrent.name,
            category=category,
            tags=tr_torrent.labels,
            is_skip_checking=skip_check,
            is_paused=True
        )

        tr_torrent_tracker_domain = urlparse(tr_torrent.trackers[0].announce).netloc
        print(f"Torrent: {tr_torrent.name} Path: {tr_torrent.download_dir} Tracker: {tr_torrent_tracker_domain}")

        time.sleep(1)


if __name__ == "__main__":
    main()
