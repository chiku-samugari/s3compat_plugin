import re
import logging
from dataclasses import dataclass

from rest_framework import status as http_status

import boto3
from botocore import exceptions

from framework.exceptions import HTTPError
from addons.base.exceptions import InvalidAuthError, InvalidFolderError
from . import settings

logger = logging.getLogger(__name__)


def connect_s3compat(host=None, access_key=None, secret_key=None, node_settings=None):
    """Helper to build an S3Connection object
    """
    if node_settings is not None:
        if node_settings.external_account is not None:
            host = node_settings.external_account.provider_id.split('\t')[0]
            access_key, secret_key = node_settings.external_account.oauth_key, node_settings.external_account.oauth_secret
            logger.info(f"s3compat.utils.connect_s3compat -- host: {host}, access_key: {access_key}, secret_key: {secret_key}")
    port = 443
    m = re.match(r'^(.+)\:([0-9]+)$', host)
    if m is not None:
        host = m.group(1)
        port = int(m.group(2))
    region = ''
    if host.endswith('.oraclecloud.com'):
        region = host.split('.')[-3]
    url = ('https://' if port == 443 else 'http://') + host
    return boto3.resource(
        's3',
        # TODO: what happens if access_key (and/or secret_key) is not
        # set? It may happen if `node_settings` is the value `None`.
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        endpoint_url=url
    )


# TODO: `ResponseMetadata` might not be returned by S3 Compatibles. We
# need to check before we use this function.
def get_status_for_error(e: exceptions.ClientError) -> int:
    return e.response['ResponseMetadata']['HTTPStatusCode']


def get_bucket_names(node_settings):
    try:
        buckets = connect_s3compat(node_settings=node_settings).buckets.all()
    except exceptions.NoCredentialsError:
        raise HTTPError(http_status.HTTP_403_FORBIDDEN)
    except exceptions.ClientError as e:
        raise HTTPError(e.status)

    return [bucket.name for bucket in buckets]


def find_service_by_host(host):
    services = [s for s in settings.AVAILABLE_SERVICES if s['host'] == host]
    if len(services) == 0:
        raise KeyError(host)
    return services[0]


def validate_bucket_location(node_settings, location):
    if location == '':
        return True
    host = node_settings.external_account.provider_id.split('\t')[0]
    service = find_service_by_host(host)
    return location in service['bucketLocations']


def validate_bucket_name(name):
    """Make sure the bucket name conforms to Amazon's expectations as described at:
    http://docs.aws.amazon.com/AmazonS3/latest/dev/BucketRestrictions.html#bucketnamingrules
    The laxer rules for US East (N. Virginia) are not supported.
    """
    label = r'[a-z0-9]+(?:[a-z0-9\-]*[a-z0-9])?'
    validate_name = re.compile('^' + label + '(?:\\.' + label + ')*$')
    is_ip_address = re.compile(r'^[0-9]+(?:\.[0-9]+){3}$')
    return (
        len(name) >= 3 and len(name) <= 63 and bool(validate_name.match(name)) and not bool(is_ip_address.match(name))
    )


def create_bucket(node_settings, bucket_name, location=''):
    # TODO: handle error?
    return connect_s3compat(node_settings=node_settings).create_bucket(Bucket=bucket_name)
    #     CreateBucketConfigurationlocation={'LocationConstraint': location})

def bucket_exists(host, access_key, secret_key, bucket_name):
    """Tests for the existance of a bucket and if the user
    can access it with the given keys
    """
    if not bucket_name:
        return False
    # TODO: should `bucket_name` lowercased? see
    # `s3.utils.bucket_exists`.

    connection = connect_s3compat(host, access_key, secret_key)

    try:
        connection.meta.client.head_bucket(Bucket=bucket_name)
    except exceptions.ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        if e.response['Error']['Code'] == '404':
            return False
        # But, `s3.utils.bucket_exists` checks if that is not `301` or `302`.
        # TODO: Which is correct? Investigate and judge.
        #       In addition, `get_status_for_error` function might be
        #       inproper for S3 Compatibles.
        # if get_status_for_error(e) not in (301, 302):
        #     return False
    return True


def can_list(host, access_key, secret_key):
    """Return whether or not a user can list
    all buckets accessable by this keys
    """
    # Bail out early as boto does not handle getting
    # Called with (None, None)
    if not (host and access_key and secret_key):
        return False

    try:
        connect_s3compat(host, access_key, secret_key).buckets.all()
    except exceptions.ClientError:
        return False
    return True


@dataclass(slots=True, frozen=True)
class Owner:
    display_name: str
    id: str

    @classmethod
    def from_dict(cls, data):
        return cls(data['DisplayName'], data['ID'])


def get_user_info(host, access_key, secret_key):
    """Returns S3 Compatible Storage User info, or None"""
    if not (access_key and secret_key):
        return None

    try:
        connection = connect_s3compat(host, access_key, secret_key)
        response = connection.meta.client.list_buckets()
        if 'Owner' in response:
            return Owner.from_dict(response['Owner'])
        else:
            return Owner(display_name=access_key, id=access_key)
    except ClientError:
        return None

def get_bucket_location_or_error(host, access_key, secret_key, bucket_name):
    """Returns the location of a bucket or raises AddonError
    """
    try:
        # Will raise an exception if bucket_name doesn't exist
        connection = connect_s3compat(host, access_key, secret_key)
        # return connection.get_bucket(bucket_name, validate=False).get_location()
        metadata = connection.meta.client.head_bucket(Bucket=bucket_name)
        return metadata['ResponseMetadata']['HTTPHeaders']['x-amz-bucket-region']
    except exceptions.NoCredentialsError:
        raise InvalidAuthError()
    except exceptions.ClientError:
        raise InvalidFolderError()
