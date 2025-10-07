import dataclasses

import boto3
from botocore import exceptions as BotoExceptions
from django.core.exceptions import ValidationError

from addon_toolkit.credentials import (
    AccessKeySecretKeyCredentials,
    Credentials,
)
from addon_toolkit.interfaces import storage


@dataclasses.dataclass
class StorageAddonClientConnectorImp[T](storage.StorageAddonClientRequestorImp):
    """base class for storage addon with fully configurable client
    """

    config: dataclasses.InitVar[storage.StorageConfig]

    # def __post_init__(self, config, credentials):
    # InitVar argument order is not fixed.
    #  https://github.com/python/cpython/issues/91507
    def __post_init__(self, *args):
        credentials, config = None, None
        if isinstance(args[0], storage.StorageConfig):
            credentials, config = args[1], args[0]
        else:
            credentials, config = args[0], args[1]

        self.config = config
        print(f"__post_init__ -- {self.config}")

        # print(f"StorageAddonClientConnectorImp.__post_init__ -- {config}, {credentials}")
        # skip the `super().__post_init__()` call since it does not pass
        # `config` instance.
        self.client = self.create_client(credentials, config)

    @staticmethod
    def create_client(credentials, config) -> T:
        raise NotImplementedError


class S3CompatStorageImp(StorageAddonClientConnectorImp):
    """Storage addon for S3 Compatible Storages
    """

    @classmethod
    def confirm_credentials(cls, credentials):
        if(len(credentials.access_key) == 0):
            raise ValidationError("Access Key cannot be an empty string.")
        if(len(credentials.secret_key) == 0):
            raise ValidationError("Secret Key cannot be an empty string.")

    def validate_connection(self):
        try:
            self.client.list_buckets()
        except BotoExceptions.ClientError:
            raise ValidationError("Fail to validate the connection")

    @staticmethod
    def validate_connection_resource_approach(credentials: AccessKeySecretKeyCredentials):
        return boto3.resource(
            "s3",
            aws_access_key_id=credentials.access_key,
            aws_secret_access_key=credentials.secret_key,
            # region= ??? it is only for oraclecloud, work on it later
            #endpoint_url=
        )

    @staticmethod
    def create_client(
            credentials: AccessKeySecretKeyCredentials,
            config: storage.StorageConfig
    ):
        kwargs = {
            "aws_access_key_id": credentials.access_key,
            "aws_secret_access_key": credentials.secret_key,
            "endpoint_url": config.external_api_url,
        }
        # TODO: how to do it?
        # if region:
        #     kwargs["region_name"] = region
        return boto3.client("s3", **kwargs)

    async def get_external_account_id(self, auth_result_extras: dict[str, str]) -> str:
        print(f"S3CompatStorageImp.get_external_account_id")
        for key, value in auth_result_extras.items():
            print(f"  {key} ({type(key).__name__}): {value} ({type(value).__name__})")
        return ""

    async def list_root_items(self, page_cursor: str = "") -> storage.ItemSampleResult:
        print(f"S3CompatStorageImp.list_root_items -- page_cursor: [{page_cursor}], [{self.config}]")
        results = list(self.list_buckets())
        return storage.ItemSampleResult(
            items=results,
            total_count=len(results),
        )

    async def list_child_items(
        self,
        item_id: str,
        page_cursor: str = "",
        item_type: storage.ItemType | None = None,
    ) -> storage.ItemSampleResult:
        print(f"S3CompatStorageImp.list_child_items -- item_id: [{item_id}], item_type: [{item_type}]")

        if ":/" not in item_id:
            # Return empty result for invalid item_id
            return storage.ItemSampleResult(items=[], total_count=0)

        bucket, key = item_id.split(":/", 1)
        print(f"  bucket: [{bucket}], key: [{key}]")

        # Ensure key ends with "/" for folder-like behavior or is empty for root
        if not key or key.endswith("/"):
            try:
                # Use list_objects_v2 (modern API) instead of list_objects
                response = self.client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=key,
                    Delimiter="/"
                )
                print(f"  API response keys: {list(response.keys())}")
                print(f"  KeyCount: {response.get('KeyCount', 0)}")
                print(f"  Contents: {response.get('Contents', 'no-contents')}")

                if('Contents' in response):
                    await self.get_item_info(f"{bucket}:/{response['Contents'][1]['Key']}")

                results = []

                # Process folders (CommonPrefixes)
                if response.get("CommonPrefixes") and (
                    item_type is None or item_type == storage.ItemType.FOLDER
                ):
                    print(f"  Processing {len(response['CommonPrefixes'])} folders")
                    for folder in response["CommonPrefixes"]:
                        folder_prefix = folder["Prefix"]
                        # Extract folder name (remove trailing slash and get last part)
                        folder_name_parts = folder_prefix.rstrip("/").split("/")
                        folder_name = folder_name_parts[-1] + "/"

                        print(f"    Folder: {folder_prefix} -> {folder_name}")
                        results.append(
                            storage.ItemResult(
                                item_id=f'{bucket}:/{folder_prefix}',
                                item_name=folder_name,
                                item_type=storage.ItemType.FOLDER,
                            )
                        )

                # Process files (Contents)
                if response.get("Contents") and (
                    item_type is None or item_type == storage.ItemType.FILE
                ):
                    print(f"  Processing {len(response['Contents'])} files")
                    for file_obj in response["Contents"]:
                        file_key = file_obj["Key"]
                        # Skip "folder" entries (keys ending with /)
                        if file_key.endswith("/"):
                            continue

                        # Extract file name (get last part after /)
                        file_name_parts = file_key.split("/")
                        file_name = file_name_parts[-1]

                        print(f"    File: {file_key} -> {file_name}")
                        results.append(
                            storage.ItemResult(
                                item_id=f'{bucket}:/{file_key}',
                                item_name=file_name,
                                item_type=storage.ItemType.FILE,
                            )
                        )

                print(f"  Returning {len(results)} items")
                return storage.ItemSampleResult(
                    items=results,
                    total_count=len(results),
                )

            except Exception as e:
                print(f"  Error listing objects: {e}")
                return storage.ItemSampleResult(items=[], total_count=0)

        # If key doesn't end with "/", this might be a file request
        # Return empty result for now (could implement single file info here)
        print(f"  Key doesn't end with '/': {key}")
        return storage.ItemSampleResult(items=[], total_count=0)

    def list_buckets(self):
        for bucket in self.client.list_buckets()["Buckets"]:
            yield storage.ItemResult(
                item_id=bucket["Name"] + ":/",
                item_name=bucket["Name"] + "/",
                item_type=storage.ItemType.FOLDER,
            )

    async def build_wb_config(self) -> dict:
        print(f"S3CompatStorageImp.build_wb_config -- {self.config}")
        return {
            "host": self.config.external_api_url,
            "bucket": self.config.connected_root_id.split(":/")[0],
            "id": self.config.connected_root_id,
            "encrypt_uploads": True,
        }

    async def get_item_info(self, item_id: str) -> storage.ItemResult:
        """Get information about a specific item (file or folder) in S3-compatible storage"""
        print(f"S3CompatStorageImp.get_item_info -- item_id: [{item_id}]")

        if not item_id or ":/" not in item_id:
            print(f"  Invalid item_id format: {item_id}")
            return None

        bucket, key = item_id.split(":/", 1)
        print(f"  bucket: [{bucket}], key: [{key}]")

        if key:
            # This is an item in a bucket (file or folder)
            try:
                # Use list_objects_v2 to check what this key represents
                response = self.client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=key,
                    Delimiter="/"
                )
                print(f"  API response - KeyCount: {response.get('KeyCount', 0)}")
                print(f"  Has Contents: {bool(response.get('Contents'))}")
                print(f"  Has CommonPrefixes: {bool(response.get('CommonPrefixes'))}")

                # Check if this is a single file
                if response.get("Contents"):
                    # Look for exact key match
                    exact_match = None
                    for content in response["Contents"]:
                        if content["Key"] == key and not content["Key"].endswith("/"):
                            exact_match = content
                            break

                    if exact_match:
                        # This is a file
                        file_name = key.split("/")[-1]  # Extract filename
                        print(f"  Found file: {key} -> {file_name}")
                        return storage.ItemResult(
                            item_id=f"{bucket}:/{exact_match['Key']}",
                            item_name=file_name,
                            item_type=storage.ItemType.FILE,
                        )

                    # If we have contents but no exact match, and no CommonPrefixes,
                    # this might be a folder with files
                    if not response.get("CommonPrefixes"):
                        # Multiple files with this prefix = folder
                        folder_name_parts = key.rstrip("/").split("/")
                        folder_name = folder_name_parts[-1] + "/"
                        print(f"  Folder with files: {key} -> {folder_name}")
                        return storage.ItemResult(
                            item_id=item_id,
                            item_name=folder_name,
                            item_type=storage.ItemType.FOLDER,
                        )

                # Check if this is a folder (has CommonPrefixes or key ends with /)
                if response.get("CommonPrefixes") or key.endswith("/"):
                    folder_name_parts = key.rstrip("/").split("/")
                    folder_name = folder_name_parts[-1] + "/"
                    print(f"  Found folder: {key} -> {folder_name}")
                    return storage.ItemResult(
                        item_id=item_id,
                        item_name=folder_name,
                        item_type=storage.ItemType.FOLDER,
                    )

                # If we get here, the item might not exist
                print(f"  No matching item found for key: {key}")
                return None

            except BotoExceptions.ClientError as e:
                print(f"  ClientError checking item: {e}")
                # Try to determine if it's a "not found" vs other error
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['NoSuchKey', 'NoSuchBucket']:
                    return None
                # For other errors, re-raise
                raise
            except Exception as e:
                print(f"  Unexpected error: {e}")
                return None

        else:
            # This is a bucket reference (key is empty)
            bucket_name = bucket.strip(":/")
            print(f"  Checking if bucket exists: {bucket_name}")
            try:
                # Check if the bucket exists using head_bucket
                self.client.head_bucket(Bucket=bucket_name)
                print(f"  Bucket exists: {bucket_name}")
                return storage.ItemResult(
                    item_id=item_id,
                    item_name=bucket_name + "/",  # Display bucket name with slash
                    item_type=storage.ItemType.FOLDER,
                )
            except BotoExceptions.ClientError as e:
                print(f"  Bucket check failed: {e}")
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'NoSuchBucket':
                    print(f"  Bucket does not exist: {bucket_name}")
                return None
            except Exception as e:
                print(f"  Unexpected error checking bucket: {e}")
                return None
