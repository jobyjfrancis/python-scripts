# Usage:
    # python3 restore-ssl-parameters.py --region <region> --file <json file> --account <account>

# example: 
    # python3 restore-ssl-parameters.py --region ap-southeast-2 --file denver-ap-southeast-2.json --account denver

import json
import re
import subprocess
import argparse

parser = argparse.ArgumentParser(description="Restore parameters")

parser.add_argument('--account', required=True, help='AWS account to use')
parser.add_argument('--region', required=True, help='AWS region to use')
parser.add_argument('--file', required=True, help='Path to the JSON file')

args = parser.parse_args()

file_name = args.file
region = args.region
account = args.account

with open(file_name, 'r') as f:
        data = json.load(f)

# Generate a list of parameter names that match /MunaVault/cluster-stack-env/sslcert/dashboard        
def generate_ssl_parameters():
    
    pattern = re.compile(r"^/MyVault/.+/sslcert/dashboard/.+/.+$")    

    matching_names = [
        param['Name']
        for param in data.get('Parameters', [])
        if pattern.match(param.get('Name', ''))
    ]

    return matching_names

# Go through the parameter name list that matches /MyVault/cluster-stack-env/sslcert/dashboard and do ssm put-parameter
def restore_ssl_parameters(name):
    for param in data.get('Parameters', []):
        if param.get('Name') == name:
            value = param.get('Value')
            command = [
            'aws-vault', 'exec', account, '--', 'aws', 'ssm', 'put-parameter',
            '--name', name,
            '--value', value,
            '--type', 'SecureString',
            '--tags', 'Key=prism:encoded,Value=true',
            '--region', region
        ]
            
        # For testing
        #     
        #     command = [
        #     'aws-vault', 'exec', account, '--', 'aws', 'ssm', 'get-parameter',
        #     '--name', name,
        #     '--region', region
        # ]
        
            try:
                result = subprocess.run(command, check=True, capture_output=True, text=True)
                print(result.stdout)
            except subprocess.CalledProcessError as e:
                print(f"Error updating {name}: {e.stderr}") 
        

ssl_parameters = generate_ssl_parameters()   

for name in ssl_parameters:
    restore_ssl_parameters(name) 

    