import os
import boto3

s3 = boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
    )

def write_file(file_content, file_name):
    s3.put_object(Body=file_content, Bucket='ask-nova-media', Key=file_name)

def read_file(file_name):
    response = s3.get_object(Bucket='ask-nova-media', Key=file_name)
    file_content = response['Body'].read()

    return file_content
