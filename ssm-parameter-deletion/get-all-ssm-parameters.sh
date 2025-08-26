#!/bin/bash

ACCOUNTS=("cosmos" "aurora" "achilles" "troy" "hector" "zion")
REGIONS=("ap-southeast-2" "us-west-2" "eu-west-1")

#ACCOUNTS=("denver" "paris" "lisbon") # For testing

for account in "${ACCOUNTS[@]}"
    do
        for region in "${REGIONS[@]}"
            do
                if $(aws-vault exec $account -- aws ssm get-parameters-by-path --path "/MyVault/" --recursive --output json --with-decryption --region $region | sed 's/\t/\n/g' > $account-$region.json);then
                    echo "$account ($region) - get-parameters finished"
                    if $(jq -e '.Parameters | length == 0' $account-$region.json > /dev/null 2>&1); then
                        echo -e "$account ($region) - parameter store is empty - no contents\n"
                        rm $account-$region.json
                    else
                        if $(aws-vault exec cosmos -- aws s3 cp --quiet $account-$region.json s3://cosmos-backup/ssm-parameters/); then
                            echo -e "$account ($region) - parameters successfully uploaded to S3 bucket s3://cosmos-backup/ssm-parameters\n"
                        else
                            echo -e "$account ($region) - parameters upload to S3 failed\n"
                        fi
                    fi
                else
                    echo "$account ($region) - get-parameters failed"
                fi
        done    
done 