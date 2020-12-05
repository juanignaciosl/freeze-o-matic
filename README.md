# Freeze-o-matic

A backup tool for files that you expect to never have to read again.

This is essentially a personal project for backing up my own files into a S3 bucket with Glacier Deep Archive, so don't
expect anything too sophisticated ;) Use this at your own risk.

## Install

    python3 -m venv _python
    source _python/bin/activate
    pip install -r requirements.txt

## Manual S3 setup

1. Go to AWS console, go to S3 and create a new bucket.
2. The storage settings are at object level, not at bucket level, so create a folder, and then select it and set Glacier
   Deep Archive as storage class at Actions -> Select storage class.

## Selecting what to back up

Copy `freezer.example.csv` to a known location and add there one line per path that you want to upload. Each file has
the following elements, separated by commas:

- Source file (if it's a relative path, it must be relative to the path that you run it from).
- Target path in the S3.
- Storage class. One of the following: STANDARD, REDUCED_REDUNDANCY, STANDARD_IA, ONEZONE_IA, INTELLIGENT_TIERING,
  GLACIER, DEEP_ARCHIVE, OUTPOSTS. Defaults to DEEP_ARCHIVE.
- force/nothing: whether the file should be always uploaded, no matter the status at the lock file. Useful for the
  freezer files, for example.

Example:

    freezer.example.csv,freezer.example.csv,STANDARD,force

That declares that you want to back up the freezer.example.csv file to the root of the bucket, with the same name.
You're highly encouraged to back up the freezer and lock (see Running section) files as well (in STANDARD mode). Add
them at the end of the file, so they're copied after all other files are.

### Directory backup

If you want to back up a full directory instead of a file, write the directory as the source and as target, pick a path
ending in `.tar.gz`. The directory will be packed, compressed and uploaded to the target destination.

Example:

    /tmp/test,my-glacier-dir/test.tar.gz,,

_Please note the trailing commas, meaning that the default storage class (Deep Archive) will be used, and that the
upload won't be forced_.

## Running

Freeze-o-matic uses boto3 for S3 uploading, so check
[how to configure credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

    AWS_PROFILE=myprofile python -m freezeomatic.run --bucket mybucket --freezer freezer.example.csv

Running it creates a `<freezer>.lock` file in the same path as the freezer file. That file reflects the status of the
upload process.

## TODO

Things that I might eventually do:

- [x] Force upload already frozen files.
- [ ] Force upload if storage class changes.
- [ ] Support for the download lifecycle.
- [ ] Check if files at the freezer should actually be uploaded or not (if the content is different). Right now, as a
  file is marked as frozen at the lock file, it won't be uploaded.
