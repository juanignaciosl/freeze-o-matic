from __future__ import annotations
import csv
import os
from argparse import ArgumentParser
from dataclasses import dataclass, replace
from enum import Enum
from typing import List

import boto3

from freezeomatic.utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FreezerEntry:
    source_path: str
    target_path: str


class LockStatus(Enum):
    PENDING = '00-pending'
    FREEZING = '10-freezing'
    FROZEN = '20-frozen'
    DEPRECATED = '90-deprecated'


UPLOADED_STATUSES = {LockStatus.FROZEN, LockStatus.DEPRECATED}


@dataclass
class FreezerLockEntry:
    target_path: str
    source_path: str
    status: LockStatus

    def deprecate(self) -> FreezerLockEntry:
        return replace(self, status=LockStatus.DEPRECATED)

    def uploaded(self) -> bool:
        return self.status in UPLOADED_STATUSES


def freeze(bucket: str, freezer_path: str) -> int:
    freezer_entries = _read_freezer(freezer_path)
    lock_path = f'{freezer_path}.lock'
    freezer_lock_entries = _read_lock(lock_path)

    updated_lock_entries = _update_lock_entries(freezer_entries,
                                                freezer_lock_entries)
    _upload(lock_path, updated_lock_entries, bucket)

    return 0


def _read_freezer(path: str) -> List[FreezerEntry]:
    freezer = []
    with open(path, newline='') as freezer_file:
        reader = csv.reader(freezer_file, delimiter=',')
        for row in reader:
            freezer.append(FreezerEntry(*row))
    return freezer


def _read_lock(lock_path: str) -> List[FreezerLockEntry]:
    lock = []
    if os.path.isfile(lock_path):
        with open(lock_path) as lock_file:
            reader = csv.reader(lock_file, delimiter=',')
            for row in reader:
                lock.append(
                    FreezerLockEntry(row[0], row[1], LockStatus(row[2])))
    return lock


def _update_lock_entries(freezer_entries: List[FreezerEntry],
                         lock_entries: List[FreezerLockEntry]) \
        -> List[FreezerLockEntry]:
    updated = []
    for freezer_entry in freezer_entries:
        lock_entry = next((le for le in lock_entries if
                           le.target_path == freezer_entry.target_path), None)
        if not lock_entry:
            lock_entry = FreezerLockEntry(
                freezer_entry.target_path,
                freezer_entry.source_path,
                LockStatus.PENDING)
        updated.append(lock_entry)

    for lock_entry in lock_entries:
        entry = next((fe for fe in freezer_entries if
                      fe.target_path == lock_entry.target_path), None)
        if not entry:
            updated.append(lock_entry.deprecate())

    return updated


def _upload(lock_path: str, lock_entries: List[FreezerLockEntry],
            bucket: str) -> None:
    s3 = boto3.client('s3')
    _dump_lock(lock_path, lock_entries)
    pending = [e for e in lock_entries if not e.uploaded()]
    for entry in pending:
        entry.status = LockStatus.FREEZING
        _dump_lock(lock_path, lock_entries)
        logger.debug(f'Uploading {entry}...')
        s3.upload_file(entry.source_path, bucket, entry.target_path,
                       ExtraArgs={'ServerSideEncryption': 'AES256'})
        entry.status = LockStatus.FROZEN
        _dump_lock(lock_path, lock_entries)


def _dump_lock(path: str, entries: List[FreezerLockEntry]) -> None:
    with open(path, 'w') as lock_file:
        writer = csv.writer(lock_file, delimiter=',')
        for entry in entries:
            writer.writerow(
                [entry.target_path, entry.source_path, entry.status.value])


def main() -> int:
    parser = ArgumentParser('Freeze-o-matic')
    parser.add_argument('--bucket', type=str, required=True)
    parser.add_argument('--freezer', type=str, required=True)
    args = parser.parse_args()

    return freeze(args.bucket, args.freezer)


if __name__ == '__main__':
    exit(main())
