# Usage
# aws-vault exec <account> -- python3 take_rds_snapshot.py --database <cluster>-<stack>-<env> --region <aws-region>

import boto3
import argparse

parser = argparse.ArgumentParser(description="Take RDS snapshot")
parser.add_argument('--database', required=True, help='database')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()

DB_INSTANCE_IDENTIFIER = args.database
AWS_REGION = args.region

SNAPSHOT_IDENTIFIER = f"{DB_INSTANCE_IDENTIFIER}-snapshot"

rds = boto3.client('rds', region_name=AWS_REGION)

def create_snapshot():
    print(f"Creating snapshot for RDS instance '{DB_INSTANCE_IDENTIFIER}'...")
    try:
        rds.create_db_snapshot(
        DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER,
        DBSnapshotIdentifier=SNAPSHOT_IDENTIFIER
        )
        print(f"Snapshot started: {SNAPSHOT_IDENTIFIER}")
        return SNAPSHOT_IDENTIFIER
    except Exception as e:
        print(f"Error creating snapshot: {e}")

def wait_for_snapshot(snapshot_id):
    print(f"Waiting for snapshot '{snapshot_id}' to become available...")
    waiter = rds.get_waiter('db_snapshot_available')
    try:
        waiter.wait(
            DBSnapshotIdentifier=snapshot_id,
            WaiterConfig={
                'Delay': 30,  
                'MaxAttempts': 20  
            }
        )
        print("Snapshot is now available.")
    except Exception as e:
        print(f"Error while waiting for snapshot: {e}")

if __name__ == "__main__":
    snapshot_id = create_snapshot()
    if snapshot_id:
        wait_for_snapshot(snapshot_id)
