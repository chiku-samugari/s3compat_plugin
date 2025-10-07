import os
import re
import hashlib
import logging
import xml.sax.saxutils
from urllib.parse import unquote, quote

import xmltodict
from aiobotocore.config import AioConfig
from aiobotocore.session import get_session

from waterbutler.core import streams, provider, exceptions
from waterbutler.core.path import WaterButlerPath
from waterbutler.core.utils import make_disposition
from s3compat_plugin.provider import settings
from s3compat_plugin.provider.metadata import (
    S3CompatRevision,
    S3CompatFileMetadata,
    S3CompatFolderMetadata,
    S3CompatFolderKeyMetadata,
    S3CompatFileMetadataHeaders,
)

logger = logging.getLogger(__name__)


class S3CompatProvider(provider.BaseProvider):
    """Provider for S3 Compatible Storage service.

    This provider supports any S3-compatible storage service including:
    - MinIO
    - Ceph Object Storage
    - DigitalOcean Spaces
    - Wasabi
    - And other S3-compatible services

    The key difference from the standard S3 provider is the ability to specify
    custom endpoints for S3-compatible services.
    """

    NAME = 's3compat'
    CHUNK_SIZE = settings.CHUNK_SIZE
    CONTIGUOUS_UPLOAD_SIZE_LIMIT = settings.CONTIGUOUS_UPLOAD_SIZE_LIMIT

    def __init__(self, auth, credentials, settings, **kwargs):
        """
        Initialize S3Compatible provider with custom endpoint support.

        :param dict auth: Not used
        :param dict credentials: Dict containing `access_key`, `secret_key`, and `host`
        :param dict settings: Dict containing `bucket` and optional `prefix`
        """
        super().__init__(auth, credentials, settings, **kwargs)

        print(f"S3CompatProvider.__init__ -- auth")
        for key, value in auth.items():
            print(f"  {key} ({type(key).__name__}): {value} ({type(value).__name__})")
        print(f"S3CompatProvider.__init__ -- credentials")
        for key, value in credentials.items():
            print(f"  {key} ({type(key).__name__}): {value} ({type(value).__name__})")
        print(f"S3CompatProvider.__init__ -- settings")
        for key, value in settings.items():
            print(f"  {key} ({type(key).__name__}): {value} ({type(value).__name__})")
        # Parse host and port from settings
        host = settings['host']
        port = 443
        is_secure = True

        # Check if host includes port
        m = re.match(r'^(.+):([0-9]+)$', host)
        if m is not None:
            host = m.group(1)
            port = int(m.group(2))
            is_secure = port == 443

        # Parse protocol from host if present
        if host.startswith('http://'):
            host = host[7:]
            is_secure = False
            if port == 443:
                port = 80
        elif host.startswith('https://'):
            host = host[8:]
            is_secure = True
            if port == 80:
                port = 443

        self.host = host
        self.port = port
        self.is_secure = is_secure
        self.endpoint_url = f"{'https' if is_secure else 'http'}://{host}:{port}"

        self.aws_secret_access_key = credentials['secret_key']
        self.aws_access_key_id = credentials['access_key']
        self.bucket_name = settings['bucket']
        self.prefix = settings.get('id', ':/').split(':/')[1]
        print(f"S3CompatProvider.__init__ -- self.prefix: {self.prefix}")
        self.encrypt_uploads = self.settings.get('encrypt_uploads', False)

    async def validate_v1_path(self, path, **kwargs):
        wbpath = WaterButlerPath(path, prepend=self.prefix)
        if path == '/':
            return wbpath

        implicit_folder = path.endswith('/')

        prefix = wbpath.full_path.lstrip('/')  # '/' -> '', '/A/B' -> 'A/B'

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                if implicit_folder:
                    # Check if folder exists by listing with prefix
                    params = {
                        'Bucket': self.bucket_name,
                        'Prefix': prefix,
                        'Delimiter': '/',
                        'MaxKeys': 1
                    }
                    resp = await s3_client.list_objects_v2(**params)
                    if not resp.get('Contents') and not resp.get('CommonPrefixes'):
                        raise exceptions.NotFoundError(str(prefix))
                else:
                    # Check if file exists
                    try:
                        await s3_client.head_object(Bucket=self.bucket_name, Key=prefix)
                    except Exception:
                        raise exceptions.NotFoundError(str(prefix))

        except exceptions.NotFoundError:
            raise
        except Exception as e:
            raise exceptions.MetadataError(str(e))

        return wbpath

    async def validate_path(self, path, **kwargs):
        return WaterButlerPath(path, prepend=self.prefix)

    def can_duplicate_names(self):
        return True

    def can_intra_copy(self, dest_provider, path=None):
        # S3-compatible storage can do server-side copy if same provider type and host
        return (
            isinstance(dest_provider, S3CompatProvider) and
            self.host == dest_provider.host and
            self.port == dest_provider.port
        )

    def can_intra_move(self, dest_provider, path=None):
        # Intra-move is copy + delete for S3-compatible storage
        return self.can_intra_copy(dest_provider, path)

    async def intra_copy(self, dest_provider, source_path, dest_path):
        """Copy key from one S3 Compatible Storage bucket to another on the same server."""
        exists = await dest_provider.exists(dest_path)

        # Ensure no leading slash when joining paths
        source_key = source_path.full_path.lstrip('/')
        dest_key = dest_path.full_path.lstrip('/')
        copy_source = f"{self.bucket_name}/{source_key}"

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=dest_provider.aws_secret_access_key,
                aws_access_key_id=dest_provider.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                await s3_client.copy_object(
                    Bucket=dest_provider.bucket_name,
                    CopySource=copy_source,
                    Key=dest_key
                )
        except Exception as e:
            raise exceptions.IntraCopyError(str(e))

        return (await dest_provider.metadata(dest_path)), not exists

    async def download(self, path, accept_url=False, version=None, range=None, **kwargs):
        """Download a file from S3 Compatible Storage."""
        if path.is_dir:
            raise exceptions.DownloadError('Cannot download folders')

        key = path.full_path.lstrip('/')

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                params = {'Bucket': self.bucket_name, 'Key': key}
                if version:
                    params['VersionId'] = version
                if range:
                    params['Range'] = range

                resp = await s3_client.get_object(**params)

                stream = streams.ResponseStreamReader(resp['Body'])
                stream.add_writer('md5', hashlib.md5())

                return stream
        except Exception as e:
            raise exceptions.DownloadError(str(e))

    async def upload(self, stream, path, conflict='replace', **kwargs):
        """Upload a file to S3 Compatible Storage."""
        key = path.full_path.lstrip('/')

        # Check for conflict
        exists = await self.exists(path)
        if exists and conflict == 'keep':
            return await self.metadata(path), False

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                # Read stream into bytes for upload
                data = await stream.read()

                params = {
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'Body': data
                }

                if self.encrypt_uploads:
                    params['ServerSideEncryption'] = 'AES256'

                await s3_client.put_object(**params)

        except Exception as e:
            raise exceptions.UploadError(str(e))

        return await self.metadata(path), not exists

    async def delete(self, path, confirm_delete=0, **kwargs):
        """Delete a file or folder from S3 Compatible Storage."""
        if path.is_file:
            key = path.full_path.lstrip('/')

            try:
                session = get_session()
                config = AioConfig(signature_version='s3v4')

                async with session.create_client(
                    's3',
                    endpoint_url=self.endpoint_url,
                    aws_secret_access_key=self.aws_secret_access_key,
                    aws_access_key_id=self.aws_access_key_id,
                    config=config,
                    use_ssl=self.is_secure
                ) as s3_client:
                    await s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            except Exception as e:
                raise exceptions.DeleteError(str(e))
        else:
            # For folders, delete all objects with the prefix
            await self._delete_folder(path, confirm_delete)

    async def _delete_folder(self, path, confirm_delete=0):
        """Delete all objects under a folder prefix."""
        prefix = path.full_path.lstrip('/')
        if not prefix.endswith('/'):
            prefix += '/'

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                # List all objects with the prefix
                paginator = s3_client.get_paginator('list_objects_v2')
                delete_keys = []

                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            delete_keys.append({'Key': obj['Key']})

                if not delete_keys:
                    return

                # Check confirmation
                if confirm_delete != len(delete_keys):
                    raise exceptions.DeleteError(
                        f'confirm_delete ({confirm_delete}) does not match the number of files to delete ({len(delete_keys)})'
                    )

                # Batch delete (S3 supports up to 1000 objects per request)
                for i in range(0, len(delete_keys), 1000):
                    batch = delete_keys[i:i+1000]
                    await s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': batch}
                    )
        except exceptions.DeleteError:
            raise
        except Exception as e:
            raise exceptions.DeleteError(str(e))

    async def metadata(self, path, revision=None, **kwargs):
        """Get metadata for a file or folder."""
        if path.is_file:
            return await self._file_metadata(path, revision)
        else:
            return await self._folder_metadata(path)

    async def _file_metadata(self, path, revision=None):
        """Get metadata for a file."""
        key = path.full_path.lstrip('/')

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                params = {'Bucket': self.bucket_name, 'Key': key}
                if revision:
                    params['VersionId'] = revision

                resp = await s3_client.head_object(**params)

                # Convert response to format expected by metadata class
                metadata_dict = {
                    'Key': key,
                    'Size': resp['ContentLength'],
                    'LastModified': resp['LastModified'],
                    'ETag': resp.get('ETag', '').strip('"'),
                    'provider': self.NAME
                }

                return S3CompatFileMetadata(self, metadata_dict)
        except Exception as e:
            raise exceptions.MetadataError(str(e))

    async def _folder_metadata(self, path):
        """Get metadata for a folder (list its contents)."""
        prefix = path.full_path.lstrip('/')
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            metadata_list = []

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                # List objects with the prefix and delimiter to get folder contents
                params = {
                    'Bucket': self.bucket_name,
                    'Prefix': prefix,
                    'Delimiter': '/'
                }

                resp = await s3_client.list_objects_v2(**params)

                # Process files (Contents)
                for obj in resp.get('Contents', []):
                    # Skip the folder itself if it appears as an object
                    if obj['Key'].endswith('/') and obj['Key'] == prefix:
                        continue

                    metadata_dict = {
                        'Key': obj['Key'],
                        'Size': obj['Size'],
                        'LastModified': obj['LastModified'],
                        'ETag': obj.get('ETag', '').strip('"'),
                        'provider': self.NAME
                    }
                    metadata_list.append(S3CompatFileMetadata(self, metadata_dict))

                # Process subfolders (CommonPrefixes)
                for common_prefix in resp.get('CommonPrefixes', []):
                    folder_prefix = common_prefix['Prefix']
                    metadata_dict = {
                        'Key': folder_prefix,
                        'provider': self.NAME
                    }
                    metadata_list.append(S3CompatFolderKeyMetadata(self, metadata_dict))

                return metadata_list

        except Exception as e:
            raise exceptions.MetadataError(str(e))

    async def revisions(self, path, **kwargs):
        """Get revision history for a file (if versioning is enabled)."""
        key = path.full_path.lstrip('/')

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                resp = await s3_client.list_object_versions(
                    Bucket=self.bucket_name,
                    Prefix=key
                )

                versions = []
                for version in resp.get('Versions', []):
                    if version['Key'] == key:
                        versions.append(S3CompatRevision({
                            'VersionId': version['VersionId'],
                            'LastModified': version['LastModified'],
                            'provider': self.NAME
                        }))

                return versions
        except Exception as e:
            # If versioning is not enabled, return empty list
            logger.warning(f"Could not get revisions: {e}")
            return []

    async def exists(self, path):
        """Check if a file exists."""
        key = path.full_path.lstrip('/')

        try:
            session = get_session()
            config = AioConfig(signature_version='s3v4')

            async with session.create_client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
                config=config,
                use_ssl=self.is_secure
            ) as s3_client:
                await s3_client.head_object(Bucket=self.bucket_name, Key=key)
                return True
        except:
            return False

    async def zip(self, path, **kwargs):
        """Create a zip of a folder."""
        # This would require implementing zip functionality
        raise NotImplementedError("Zip functionality not yet implemented for S3Compatible provider")

    def path_from_metadata(self, parent_path, metadata):
        """Create a WaterButlerPath from metadata."""
        return parent_path.child(metadata.name, folder=metadata.is_folder)
