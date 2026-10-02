# torrent-peek

Inspect local BitTorrent v1 `.torrent` metadata without contacting trackers or peers. It prints the info hash, file count, total size, and piece summary; it never prints names, tracker URLs, or piece hashes.

## Use

Requires Python 3.8+; no packages to install.

```sh
python torrent_peek.py movie.torrent
cat metadata.torrent | python torrent_peek.py -
```

The decoder is limited to 32 MiB, 64 nesting levels, and one million bencoded items. It requires canonical, sorted bencode and checks that the v1 piece-hash count matches the total size. BitTorrent v2 and hybrid torrents are not supported. The SHA-1 info hash is the legacy v1 identifier, not a modern integrity or security guarantee. Only the summary fields above are printed; names, URLs, comments, and piece hashes are withheld. Exit status is 0 for valid v1 metadata and 1 for malformed or unreadable input.

See [BEP 3](https://www.bittorrent.org/beps/bep_0003.html) for v1 bencoding and info-hash rules, and [BEP 52](https://www.bittorrent.org/beps/bep_0052.html) for the separate v2 format.

## License

MIT
