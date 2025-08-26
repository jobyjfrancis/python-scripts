# Usage
# aws-vault exec <account> -- python3 copy_encrypt_rds_snapshot.py --source <cluster>-<stack>-<env>-snapshot --region <aws-region>

import boto3
import argparse

parser = argparse.ArgumentParser(description="Copy RDS snapshot and encrypt")
parser.add_argument('--source', required=True, help='source snapshot')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()

SOURCE_SNAPSHOT_ID = args.source
AWS_REGION = args.region

DEST_SNAPSHOT_ID = f"{SOURCE_SNAPSHOT_ID}-encrypted"

def get_default_rds_kms_arn(region=AWS_REGION):
    kms = boto3.client('kms', region_name=region)
    try:
        response = kms.describe_key(KeyId='alias/aws/rds')
        return response['KeyMetadata']['Arn']
    except Exception as e:
        print(f"Error fetching default RDS KMS key: {e}")

def copy_and_encrypt_snapshot(source_id, dest_id, kms_key=None):
    print(f"Copying and encrypting snapshot '{source_id}' to '{dest_id}'...")
    try:
        copy_params = {
            'SourceDBSnapshotIdentifier': source_id,
            'TargetDBSnapshotIdentifier': dest_id,
            'CopyTags': True,
            'OptionGroupName':'default:mysql-8-0',
            'KmsKeyId':kms_key
        }

        response = rds.copy_db_snapshot(**copy_params)
        print(f"Snapshot copy initiated: {dest_id}")
        return response['DBSnapshot']['DBSnapshotIdentifier']
    except Exception as e:
        print(f"Failed to copy/encrypt snapshot: {e}")

def wait_for_snapshot(snapshot_id):
    print(f"Waiting for encrypted snapshot '{snapshot_id}' to become available...")
    waiter = rds.get_waiter('db_snapshot_available')
    try:
        waiter.wait(
            DBSnapshotIdentifier=snapshot_id,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': 20
            }
        )
        print("Encrypted snapshot is now available.")
    except Exception as e:
        print(f"Error while waiting: {e}")

rds = boto3.client('rds', region_name=AWS_REGION)

KMS_KEY_ID = get_default_rds_kms_arn(AWS_REGION)

if __name__ == "__main__":
    copied_snapshot_id = copy_and_encrypt_snapshot(SOURCE_SNAPSHOT_ID, DEST_SNAPSHOT_ID, KMS_KEY_ID)
    if copied_snapshot_id:
        wait_for_snapshot(copied_snapshot_id)
