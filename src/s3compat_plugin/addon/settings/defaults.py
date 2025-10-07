"""Default settings for S3 Compatible Storage addon."""

ENCRYPT_UPLOADS_DEFAULT = True

import json
import os

from website.settings import parent_dir

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(parent_dir(HERE), 'static')

MAX_RENDER_SIZE = (1024 ** 2) * 3

# Max file size permitted by frontend in megabytes
MAX_UPLOAD_SIZE = 50 * 1024  # 50 GB

ALLOWED_ORIGIN = '*'

# BUCKET_LOCATIONS = {} # see addons/s3/settings/defaults.py
ENCRYPT_UPLOADS_DEFAULT = True
# Load S3 settings used in both front and back end
with open(os.path.join(STATIC_PATH, 'settings.json')) as fp:
    settings = json.load(fp)
    # BUCKET_LOCATIONS = settings.get('bucketLocations', {}) # addons/s3/settings/defaults.py
    AVAILABLE_SERVICES = settings.get('availableServices', [])
    ENCRYPT_UPLOADS_DEFAULT = settings.get('encryptUploads', True)

OSF_USER = 'osf-user{0}'
OSF_USER_POLICY_NAME = 'osf-user-policy'
OSF_USER_POLICY = json.dumps(
    {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Sid': 'Stmt1392138408000',
                'Effect': 'Allow',
                'Action': [
                    's3:*'
                ],
                'Resource': [
                    '*'
                ]
            },
            {
                'Sid': 'Stmt1392138440000',
                'Effect': 'Allow',
                'Action': [
                    'iam:DeleteAccessKey',
                    'iam:DeleteUser',
                    'iam:DeleteUserPolicy'
                ],
                'Resource': [
                    '*'
                ]
            }
        ]
    }
)

# Available S3-compatible services
S3_COMPAT_SERVICES = [
    {'name': 'IDCF Cloud', 'host': 'ds.jp-east.idcfcloud.com'},
    {'name': 'SAKURA Cloud', 'host': 's3.isk01.sakurastorage.jp:443'},
    {'name': 'Wasabi', 'host': 's3.wasabisys.com'},
    {'name': 'Wasabi Tokyo', 'host': 's3.ap-northeast-1.wasabisys.com'},
    {'name': 'Wasabi Osaka', 'host': 's3.ap-northeast-2.wasabisys.com'},
    {'name': 'Kanazawa University Cloud', 'host': 's3-kakuma.rdm.kanazawa-u.ac.jp'},
    {'name': 'Rakuten Cloud', 'host': 's3.jp3.objectstorage.rakuten-cloud.net'},
    {'name': 'mdx S3DS', 'host': 's3ds.mdx.jp'},
    {'name': 'RIKEN HSS S3', 'host': 'hssgws3.riken.jp:443'},
    {'name': 'SPring-8 Proto S3', 'host': 'sp8-s3gw.spring8.or.jp:443'},
    {'name': 'ONION-object Osaka', 'host': 's3-osakau.oniongw.hpc.cmc.osaka-u.ac.jp:443'},
    {'name': 'MinIO Kanazawa', 'host': 'minio.rdm.kanazawa-u.ac.jp:443'},
    {'name': 'MinIO-Dev Gunma', 'host': 'minio-dev.media.gunma-u.ac.jp:443'},
    {'name': 'Kagoshima RDM Storage', 'host': 's3-rdms.cc.kagoshima-u.ac.jp:443'},
    {'name': 'Hirosaki University S3', 'host': 'file-oa-s3.oa.hirosaki-u.ac.jp:443'},
    {'name': 'Ryukyus ActiveScale', 'host': 'grdm.lab.u-ryukyu.ac.jp:443'},
    {'name': 'Toyohashi RDM Storage', 'host': 'ys3ds.edu.tut.ac.jp:443'},
    {'name': 'Kyoto IIMC Storage', 'host': 's3.rdm.kyoto-u.ac.jp:443'},
    {'name': 'IZUMI Tohoku', 'host': 's3.rdx.tohoku.ac.jp:443'},
]
