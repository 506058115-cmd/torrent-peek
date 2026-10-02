#!/usr/bin/env python3
"""Summarize a BitTorrent v1 metainfo file without contacting the network."""

import argparse
import hashlib
import sys
from pathlib import Path


MAX_INPUT = 32 * 1024 * 1024
MAX_DEPTH = 64
MAX_NODES = 1_000_000


class TorrentError(ValueError):
    pass


class Decoder:
    def __init__(self, data):
        self.data = data
        self.nodes = 0
        self.info_range = None

    def string(self, position):
        colon = self.data.find(b":", position)
        if colon < 0:
            raise TorrentError("unterminated string length")
        digits = self.data[position:colon]
        if not digits or not digits.isdigit() or (len(digits) > 1 and digits.startswith(b"0")):
            raise TorrentError("invalid string length")
        try:
            size = int(digits)
        except ValueError as error:
            raise TorrentError("string length is too large") from error
        start, end = colon + 1, colon + 1 + size
        if end > len(self.data):
            raise TorrentError("string extends past end of file")
        return self.data[start:end], end

    def value(self, position=0, depth=0, root=False):
        if depth > MAX_DEPTH:
            raise TorrentError("nesting limit exceeded")
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise TorrentError("item limit exceeded")
        if position >= len(self.data):
            raise TorrentError("unexpected end of file")

        token = self.data[position]
        if 48 <= token <= 57:
            return self.string(position)
        if token == ord("i"):
            end = self.data.find(b"e", position + 1)
            if end < 0:
                raise TorrentError("unterminated integer")
            digits = self.data[position + 1:end]
            if (not digits or digits == b"-0" or digits.startswith(b"+")
                    or (digits.startswith(b"0") and len(digits) > 1)
                    or (digits.startswith(b"-") and (len(digits) == 1 or digits[1:2] == b"0"))
                    or not digits.lstrip(b"-").isdigit()):
                raise TorrentError("invalid integer")
            try:
                return int(digits), end + 1
            except ValueError as error:
                raise TorrentError("integer is too large") from error
        if token == ord("l"):
            items = []
            position += 1
            while position < len(self.data) and self.data[position] != ord("e"):
                item, position = self.value(position, depth + 1)
                items.append(item)
            if position >= len(self.data):
                raise TorrentError("unterminated list")
            return items, position + 1
        if token == ord("d"):
            result = {}
            previous = None
            position += 1
            while position < len(self.data) and self.data[position] != ord("e"):
                key, position = self.string(position)
                if previous is not None and key <= previous:
                    raise TorrentError("dictionary keys are duplicate or out of order")
                previous = key
                value_start = position
                item, position = self.value(position, depth + 1)
                result[key] = item
                if root and key == b"info":
                    self.info_range = value_start, position
            if position >= len(self.data):
                raise TorrentError("unterminated dictionary")
            return result, position + 1
        raise TorrentError("invalid bencode token")


def inspect(data):
    decoder = Decoder(data)
    metainfo, end = decoder.value(root=True)
    if end != len(data):
        raise TorrentError("trailing data after metainfo")
    if not isinstance(metainfo, dict) or not isinstance(metainfo.get(b"info"), dict):
        raise TorrentError("top-level info dictionary is missing")
    info = metainfo[b"info"]
    if b"meta version" in info:
        raise TorrentError("BitTorrent v2/hybrid metadata is not supported")

    piece_length = info.get(b"piece length")
    pieces = info.get(b"pieces")
    if not isinstance(piece_length, int) or piece_length <= 0:
        raise TorrentError("invalid piece length")
    if not isinstance(pieces, bytes) or len(pieces) % 20:
        raise TorrentError("invalid v1 pieces field")

    single_file = b"length" in info
    multi_file = b"files" in info
    if single_file == multi_file:
        raise TorrentError("info must contain either length or files")
    if single_file:
        length = info[b"length"]
        if not isinstance(length, int) or length < 0:
            raise TorrentError("invalid file length")
        file_count = 1
        total_size = length
    else:
        files = info[b"files"]
        if not isinstance(files, list) or not files:
            raise TorrentError("invalid files list")
        file_count = len(files)
        total_size = 0
        for entry in files:
            length = entry.get(b"length") if isinstance(entry, dict) else None
            if not isinstance(length, int) or length < 0:
                raise TorrentError("invalid length in files list")
            total_size += length

    piece_count = len(pieces) // 20
    expected_pieces = (total_size + piece_length - 1) // piece_length
    if piece_count != expected_pieces:
        raise TorrentError("piece hash count does not match total size")
    if decoder.info_range is None:
        raise TorrentError("raw info dictionary range is missing")
    start, finish = decoder.info_range
    info_hash = hashlib.sha1(data[start:finish]).hexdigest()
    return info_hash, file_count, total_size, piece_length, piece_count


def main():
    parser = argparse.ArgumentParser(description="Summarize BitTorrent v1 metainfo without network access.")
    parser.add_argument("input", help=".torrent file, or - to read standard input")
    args = parser.parse_args()
    try:
        if args.input == "-":
            data = sys.stdin.buffer.read(MAX_INPUT + 1)
        else:
            with Path(args.input).open("rb") as source:
                data = source.read(MAX_INPUT + 1)
        if len(data) > MAX_INPUT:
            raise TorrentError("input exceeds the 32 MiB limit")
        info_hash, file_count, total_size, piece_length, piece_count = inspect(data)
    except (OSError, TorrentError) as error:
        print(f"torrent-peek: {error}", file=sys.stderr)
        return 1

    print("Format: BitTorrent v1")
    print(f"Info hash (SHA-1): {info_hash}")
    print(f"Files: {file_count}")
    print(f"Total size: {total_size} bytes")
    print(f"Piece length: {piece_length} bytes")
    print(f"Pieces: {piece_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
