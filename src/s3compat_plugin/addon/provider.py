from .serializer import S3CompatSerializer

class S3CompatProvider(object):
    """An alternative to `ExternalProvider` not tied to OAuth"""

    name = 'S3 Compatible Storage'
    short_name = 's3compat'
    serializer = S3CompatSerializer

    def __init__(self, account=None):
        super().__init__()
        # In RDM-osf.io, both S3 and s3compat use the following style, but S3
        # implementation of  osf.io uses the **above** style. I have not yet
        # checked which is better, but follow the newer approach.
        # super(S3CompatProvider, self).__init__()

        # provide an unauthenticated session by default
        self.account = account

    def __repr__(self):
        return '<{name}: {status}>'.format(
            name=self.__class__.__name__,
            status=self.account.provider_id if self.account else 'anonymous'
        )

    def handle_callback(self, response):
        # For S3-compatible, we store access key/secret key directly
        # The provider_id includes the host to distinguish between different services
        host = response.get('host', 's3.wasabisys.com')
        access_key = response.get('access_key')

        return {
            'provider_id': f"{host}\t{access_key}",  # Format: host<tab>access_key
            'display_name': f"{access_key}@{host}",
            'access_key': access_key,
            'secret_key': response.get('secret_key'),
            'host': host,
        }
