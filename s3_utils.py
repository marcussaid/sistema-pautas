import os
import boto3
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename
from datetime import datetime

class S3Handler:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_DEFAULT_REGION')
        )
        self.bucket_name = os.environ.get('AWS_BUCKET_NAME')

    def upload_file(self, file, prefix='uploads/'):
        """
        Upload a file to S3
        """
        try:
            # Generate a secure filename with timestamp
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            s3_path = f"{prefix}{unique_filename}"

            # Upload the file
            self.s3_client.upload_fileobj(file, self.bucket_name, s3_path)

            # Generate the URL
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_path}"

            return {
                'success': True,
                'filename': unique_filename,
                'original_name': filename,
                's3_path': s3_path,
                'url': url
            }
        except ClientError as e:
            print(f"Error uploading file to S3: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def download_file(self, s3_path):
        """
        Download a file from S3
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_path)
            return response['Body'].read()
        except ClientError as e:
            print(f"Error downloading file from S3: {str(e)}")
            return None

    def delete_file(self, s3_path):
        """
        Delete a file from S3
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_path)
            return True
        except ClientError as e:
            print(f"Error deleting file from S3: {str(e)}")
            return False

    def get_file_url(self, s3_path):
        """
        Get the URL for a file in S3
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_path
                },
                ExpiresIn=3600  # URL expires in 1 hour
            )
            return url
        except ClientError as e:
            print(f"Error generating URL for S3 file: {str(e)}")
            return None
