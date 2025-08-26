import boto3

def list_rds_instances():
    client = boto3.client('rds')
    response = client.describe_db_instances()
    print("RDS instances and their sizes:")
    for db_instance in response["DBInstances"]:
        instance_id = db_instance["DBInstanceIdentifier"]
        instance_class = db_instance["DBInstanceClass"]
        print(f"Instance ID: {instance_id}, Size: {instance_class}")

if __name__ == "__main__":
    list_rds_instances()