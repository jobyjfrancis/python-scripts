import boto3
from botocore.exceptions import ClientError

def get_role_arn(role_name):
    iam = boto3.client('iam')
    try:
        response = iam.get_role(RoleName=role_name)
        arn = response['Role']['Arn']
        print(f"ARN for role '{role_name}': {arn}")
        return arn
    except ClientError as e:
        print(f"Error retrieving role ARN: {e}")
        return None

if __name__ == "__main__":
    role_name = input("Enter the IAM role name: ").strip()
    get_role_arn(role_name)
