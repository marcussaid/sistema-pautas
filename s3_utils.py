import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from werkzeug.utils import secure_filename
from datetime import datetime

class S3Handler:
    def __init__(self):
        print("[INFO] Inicializando S3Handler...")
        
        # Valores padrão do render.yaml
        default_values = {
            "AWS_ACCESS_KEY_ID": "AKIA6K5V7IBO8LCA3AX3",
            "AWS_SECRET_ACCESS_KEY": "GuVsYxyGpmIiHDZyX3udbLwEmCnq/mBRaxtPWn7p",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_BUCKET_NAME": "mybucketmarcussaidrr"
        }
        
        # Usar valores do ambiente ou fallback para valores padrão
        self.aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", default_values["AWS_ACCESS_KEY_ID"])
        self.aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", default_values["AWS_SECRET_ACCESS_KEY"])
        self.aws_region = os.environ.get("AWS_DEFAULT_REGION", default_values["AWS_DEFAULT_REGION"])
        self.bucket_name = os.environ.get("AWS_BUCKET_NAME", default_values["AWS_BUCKET_NAME"])

        print(f"[INFO] AWS_ACCESS_KEY_ID presente: {bool(self.aws_access_key_id)}")
        print(f"[INFO] AWS_SECRET_ACCESS_KEY presente: {bool(self.aws_secret_access_key)}")
        print(f"[INFO] AWS_DEFAULT_REGION: {self.aws_region}")
        print(f"[INFO] AWS_BUCKET_NAME: {self.bucket_name}")

        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )

            # Verificar se podemos acessar o bucket
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"[INFO] Conexão com bucket {self.bucket_name} estabelecida com sucesso")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "403":
                error_msg = f"[ERROR] Acesso negado ao bucket {self.bucket_name}. Verifique as credenciais AWS."
            elif error_code == "404":
                error_msg = f"[ERROR] Bucket {self.bucket_name} não encontrado."
            else:
                error_msg = f"[ERROR] Erro ao conectar ao S3: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
        except NoCredentialsError:
            error_msg = "[ERROR] Credenciais AWS inválidas"
            print(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"[ERROR] Erro ao inicializar S3Handler: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def upload_file(self, file, prefix="uploads/"):
        """
        Upload a file to S3
        """
        if not file:
            error_msg = "[ERROR] Nenhum arquivo fornecido"
            print(error_msg)
            return {"success": False, "error": error_msg}

        try:
            print(f"[INFO] Iniciando upload do arquivo {file.filename} para S3...")
            
            # Generate a secure filename with timestamp
            filename = secure_filename(file.filename)
            if not filename:
                error_msg = "[ERROR] Nome de arquivo inválido"
                print(error_msg)
                return {"success": False, "error": error_msg}

            unique_filename = f"{datetime.now().strftime("%Y%m%d%H%M%S")}_{filename}"
            s3_path = f"{prefix}{unique_filename}"

            print(f"[INFO] Nome do arquivo processado: {unique_filename}")
            print(f"[INFO] Caminho S3: {s3_path}")
            print(f"[INFO] Bucket: {self.bucket_name}")

            # Reset file pointer to beginning
            file.seek(0)

            # Upload the file
            self.s3_client.upload_fileobj(file, self.bucket_name, s3_path)

            # Generate the URL
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_path}"
            print(f"[INFO] Upload concluído. URL gerada: {url}")

            return {
                "success": True,
                "filename": unique_filename,
                "original_name": filename,
                "s3_path": s3_path,
                "url": url
            }
        except ClientError as e:
            error_msg = f"[ERROR] Erro ao fazer upload para S3: {str(e)}"
            print(error_msg)
            print(f"[ERROR] Detalhes do erro: {e.response["Error"]}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"[ERROR] Erro inesperado: {str(e)}"
            print(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    def download_file(self, s3_path):
        """
        Download a file from S3
        """
        try:
            print(f"[INFO] Baixando arquivo {s3_path} do S3...")
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_path)
            return response["Body"].read()
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
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_path
                },
                ExpiresIn=3600  # URL expires in 1 hour
            )
            return url
        except ClientError as e:
            print(f"[ERROR] Erro ao gerar URL para arquivo S3: {str(e)}")
            return None
