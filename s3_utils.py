import os
import boto3
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename
from datetime import datetime

class S3Handler:
    def __init__(self):
        # Log das variáveis de ambiente (sem mostrar valores sensíveis)
        print("[INFO] Inicializando S3Handler...")
        print(f"[INFO] AWS_ACCESS_KEY_ID presente: {bool(os.environ.get('AWS_ACCESS_KEY_ID'))}")
        print(f"[INFO] AWS_SECRET_ACCESS_KEY presente: {bool(os.environ.get('AWS_SECRET_ACCESS_KEY'))}")
        print(f"[INFO] AWS_DEFAULT_REGION: {os.environ.get('AWS_DEFAULT_REGION')}")
        print(f"[INFO] AWS_BUCKET_NAME: {os.environ.get('AWS_BUCKET_NAME')}")

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
            print(f"[INFO] Iniciando upload do arquivo {file.filename} para S3...")
            
            # Generate a secure filename with timestamp
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            s3_path = f"{prefix}{unique_filename}"

            print(f"[INFO] Nome do arquivo processado: {unique_filename}")
            print(f"[INFO] Caminho S3: {s3_path}")
            print(f"[INFO] Bucket: {self.bucket_name}")

            # Upload the file
            self.s3_client.upload_fileobj(file, self.bucket_name, s3_path)

            # Generate the URL
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_path}"
            print(f"[INFO] Upload concluído. URL gerada: {url}")

            return {
                'success': True,
                'filename': unique_filename,
                'original_name': filename,
                's3_path': s3_path,
                'url': url
            }
        except ClientError as e:
            print(f"[ERROR] Erro ao fazer upload para S3: {str(e)}")
            print(f"[ERROR] Detalhes do erro: {e.response['Error']}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            print(f"[ERROR] Erro inesperado: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def download_file(self, s3_path):
        """
        Download a file from S3
        """
        try:
            print(f"[INFO] Baixando arquivo {s3_path} do S3...")
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_path)
            return response['Body'].read()
        except ClientError as e:
            print(f"[ERROR] Erro ao baixar arquivo do S3: {str(e)}")
            return None

    def delete_file(self, s3_path):
        """
        Delete a file from S3
        """
        try:
            print(f"[INFO] Deletando arquivo {s3_path} do S3...")
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_path)
            return True
        except ClientError as e:
            print(f"[ERROR] Erro ao deletar arquivo do S3: {str(e)}")
            return False

    def get_file_url(self, s3_path):
        """
        Get the URL for a file in S3
        """
        try:
            print(f"[INFO] Gerando URL para {s3_path}...")
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
            print(f"[ERROR] Erro ao gerar URL para arquivo S3: {str(e)}")
            return None
