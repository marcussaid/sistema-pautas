import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from werkzeug.utils import secure_filename
from datetime import datetime

class S3Handler:
    def __init__(self):
        # Log das variáveis de ambiente (sem mostrar valores sensíveis)
        print("[INFO] Inicializando S3Handler...")
        
        # Verificar se todas as variáveis de ambiente necessárias estão presentes
        required_vars = {
            "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
            "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION"),
            "AWS_BUCKET_NAME": os.environ.get("AWS_BUCKET_NAME")
        }

        missing_vars = [key for key, value in required_vars.items() if not value]
        if missing_vars:
            error_msg = f"[ERROR] Variáveis de ambiente ausentes: {", ".join(missing_vars)}"
            print(error_msg)
            raise ValueError(error_msg)

        print(f"[INFO] AWS_ACCESS_KEY_ID presente: {bool(required_vars["AWS_ACCESS_KEY_ID"])}")
        print(f"[INFO] AWS_SECRET_ACCESS_KEY presente: {bool(required_vars["AWS_SECRET_ACCESS_KEY"])}")
        print(f"[INFO] AWS_DEFAULT_REGION: {required_vars["AWS_DEFAULT_REGION"]}")
        print(f"[INFO] AWS_BUCKET_NAME: {required_vars["AWS_BUCKET_NAME"]}")

        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=required_vars["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=required_vars["AWS_SECRET_ACCESS_KEY"],
                region_name=required_vars["AWS_DEFAULT_REGION"]
            )
            self.bucket_name = required_vars["AWS_BUCKET_NAME"]

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
