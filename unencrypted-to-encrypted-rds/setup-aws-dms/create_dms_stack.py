# Usage
# aws-vault exec <account> -- python3 create_dms_stack.py --stack <cluster>-<stack>-<env> --template <template_url> --region <aws-region>

import boto3
import argparse

parser = argparse.ArgumentParser(description="Create DMS stack")
parser.add_argument('--stack', required=True, help='stack')
parser.add_argument('--template', required=True, help='CF template URL')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()

stack = args.stack
cf_template_url = args.template
aws_region = args.region

cf = boto3.client('cloudformation', region_name=aws_region)

def fetch_db_password():
    response = cf.describe_stacks(
        StackName=stack
        )
    Outputs = response['Stacks'][0]['Outputs']
    for output in Outputs:
        if output['OutputKey'] == "MySQLPassword":
            mysql_password = output['OutputValue']
            
    return mysql_password

def create_dms_cf_stack(mysql_password, template_url):
    response = cf.create_stack(
        StackName=f"{stack}-dms-stack",
        TemplateURL=template_url,
        Parameters=[
            {
                'ParameterKey': 'DBPassword',
                'ParameterValue': mysql_password
            },
        ],
        Capabilities=['CAPABILITY_IAM']
    )
    return response['StackId']

def wait_for_cf_stack(cf_stack_id):
    print(f"Waiting for CF stack '{cf_stack_id}' to finish creation...")
    waiter = cf.get_waiter('stack_create_complete')
    try:
        waiter.wait(
            StackName=cf_stack_id,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': 20
            }
        )
        print(f"CF stack '{cf_stack_id}' has been created successully")
    except Exception as e:
        print(f"Error while waiting: {e}")

if __name__ == '__main__':
    mysql_password = fetch_db_password()
    dms_cf_stack_id = create_dms_cf_stack(mysql_password, cf_template_url)
    if dms_cf_stack_id:
        wait_for_cf_stack(dms_cf_stack_id)
