# Freeze-o-matic

A backup tool for files that you expect to never have to read again.

## Manual setup

1. Go to AWS console, go to S3 and create a new bucket.
2. The storage settings are at object level, not at bucket level, so create a folder,
   and then select it and set Glacier Deep Archive as storage class at Actions -> Select storage class.

