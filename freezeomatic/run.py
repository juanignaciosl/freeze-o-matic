from __future__ import annotations
import csv
import os
import subprocess
import tarfile
from argparse import ArgumentParser
from dataclasses import dataclass, replace
from enum import Enum
from tempfile import gettempdir
from typing import List, Any

import boto3

from freezeomatic.utils import get_logger

logger = get_logger(__name__)


class StorageClass(Enum):
    STANDARD = 'STANDARD'
    REDUCED_REDUNDANCY = 'REDUCED_REDUNDANCY'
    STANDARD_IA = 'STANDARD_IA'
    ONEZONE_IA = 'ONEZONE_IA'
    INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
    GLACIER = 'GLACIER'
    DEEP_ARCHIVE = 'DEEP_ARCHIVE'
    OUTPOSTS = 'OUTPOSTS'


DEFAULT_STORAGE = StorageClass.DEEP_ARCHIVE


@dataclass(frozen=True)
class FreezerEntry:
    source_path: str
    target_path: str
    storage_class: StorageClass
    force: bool


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
    storage_class: StorageClass
    status: LockStatus
    force: bool

    def deprecate(self) -> FreezerLockEntry:
        return replace(self, status=LockStatus.DEPRECATED)

    def requires_upload(self) -> bool:
        return self.status not in UPLOADED_STATUSES or self.force


def freeze(bucket: str, freezer_path: str, python_tar: bool) -> int:
    freezer_entries = _read_freezer(freezer_path)
    lock_path = f'{freezer_path}.lock'
    freezer_lock_entries = _read_lock(lock_path)

    updated_lock_entries = _update_lock_entries(freezer_entries,
                                                freezer_lock_entries)
    _upload(lock_path, updated_lock_entries, bucket, python_tar)

    return 0


def _read_freezer(path: str) -> List[FreezerEntry]:
    freezer = []
    with open(path, newline='') as freezer_file:
        reader = csv.reader(freezer_file, delimiter=',')
        for row in reader:
            freezer.append(FreezerEntry(
                source_path=row[0],
                target_path=row[1],
                storage_class=StorageClass(row[2])
                if row[2] != '' else DEFAULT_STORAGE,
                force=row[3] == 'force'
            ))
    return freezer


def _read_lock(lock_path: str) -> List[FreezerLockEntry]:
    lock = []
    if os.path.isfile(lock_path):
        with open(lock_path) as lock_file:
            reader = csv.reader(lock_file, delimiter=',')
            for row in reader:
                lock.append(
                    FreezerLockEntry(
                        target_path=row[0],
                        source_path=row[1],
                        storage_class=StorageClass(row[2]),
                        status=LockStatus(row[3]),
                        force=row[4] == 'force'
                    ))
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
                freezer_entry.storage_class,
                LockStatus.PENDING,
                freezer_entry.force)
        updated.append(lock_entry)

    for lock_entry in lock_entries:
        entry = next((fe for fe in freezer_entries if
                      fe.target_path == lock_entry.target_path), None)
        if not entry:
            updated.append(lock_entry.deprecate())

    return updated


def _upload(lock_path: str, lock_entries: List[FreezerLockEntry],
            bucket: str, python_tar: bool) -> None:
    s3 = boto3.client('s3')
    _dump_lock(lock_path, lock_entries)
    pending = [e for e in lock_entries if e.requires_upload()]
    for entry in pending:
        entry.status = LockStatus.FREEZING
        _dump_lock(lock_path, lock_entries)
        _upload_entry(s3, entry, bucket, python_tar)
        entry.status = LockStatus.FROZEN
        _dump_lock(lock_path, lock_entries)


def _upload_entry(s3: Any, entry: FreezerLockEntry, bucket: str,
                  python_tar: bool) -> None:
    source_path = entry.source_path
    target_path = entry.target_path
    storage_class = entry.storage_class
    if os.path.isfile(source_path):
        _upload_file(s3, source_path, bucket, target_path, storage_class)
    elif os.path.isdir(source_path) and target_path.endswith('tar.gz'):
        local_tgz = os.path.join(gettempdir(),
                                 f'{os.path.basename(source_path)}.tar.gz')
        logger.debug(f'Compressing {source_path} into {local_tgz}...')
        if python_tar:
            with tarfile.open(local_tgz, 'w|gz') as tar:
                tar.add(source_path, arcname=os.path.basename(source_path))
        else:
            subprocess.run(['tar', '-czf', local_tgz, source_path], check=True)

        _upload_file(s3, local_tgz, bucket, target_path, storage_class)
        os.remove(local_tgz)
    else:
        raise ValueError(f'Unsupported entry upload: {entry}')


def _upload_file(s3: Any, source_path: str, bucket: str,
                 target_path: str, storage_class: StorageClass) -> None:
    logger.debug(f'Uploading {source_path} to {target_path}...')
    s3.upload_file(source_path, bucket, target_path,
                   ExtraArgs={'ServerSideEncryption': 'AES256',
                              'StorageClass': storage_class.name})


def _dump_lock(path: str, entries: List[FreezerLockEntry]) -> None:
    with open(path, 'w') as lock_file:
        writer = csv.writer(lock_file, delimiter=',')
        for entry in entries:
            writer.writerow(
                [entry.target_path, entry.source_path,
                 entry.storage_class.name, entry.status.value,
                 'force' if entry.force else ''])


def main() -> int:
    parser = ArgumentParser('Freeze-o-matic')
    parser.add_argument('--bucket', type=str, required=True)
    parser.add_argument('--freezer', type=str, required=True)
    parser.add_argument('--python-tar', action='store_true',
                        help='Use Python tarfile instead of tar -czf')
    args = parser.parse_args()

    return freeze(args.bucket, args.freezer, args.python_tar)


if __name__ == '__main__':
    exit(main())
