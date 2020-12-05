# Freeze-o-matic

A backup tool for files that you expect to never have to read again.

This is essentially a personal project for backing up my personal files into a S3 bucket with Glacier Deep Archive, so
don't expect anything too sophisticated ;)

## Install

    python3 -m venv _python
    source _python/bin/activate
    pip install -r requirements.txt

## Manual S3 setup

1. Go to AWS console, go to S3 and create a new bucket.
2. The storage settings are at object level, not at bucket level, so create a folder, and then select it and set Glacier
   Deep Archive as storage class at Actions -> Select storage class.

## Selecting what to backup

Copy `freezer.example.csv` to a known location and add there one line per path that you want to upload. Each file has
two elements, separated by commas:

- Source file (if it's a relative path, it must be relative to the path that you run it from).
- Target path in the S3.

Example:

    freezer.example.csv,freezer.example.csv

That declares that you want to backup the freezer.example.csv file to the root of the bucket, with the same name. You're
highly encourage to backup the freezer and lock (see Running section) files as well. Add them at the end of the file so
they're copied after all other files are.

## Running

Freeze-o-matic uses boto3 for S3 uploading, so check
[how to configure credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

    AWS_PROFILE=myprofile python -m freezeomatic.run --bucket mybucket --freezer freezer.example.csv

Running it creates a `<freezer>.lock` file in the same path than the freezer file. That file reflects the status of the
upload process.
